# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=duplicate-code
# pylint: disable=no-raise-unlink
# pylint: disable=translation-not-lazy
# pylint: disable=translation-positional-used

import logging
import re
from datetime import date

from jinja2 import Environment, StrictUndefined, TemplateError
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Jinja2 template variable shortcuts (used in billable_item_detail_desc and aux_desc)
JINJA2_TEMPLATE_SHORTCUTS = {
    "billable_item": "Record from billable model (e.g. parcel, unit)",
    "first_q": "Q1/YYYY (e.g. Q1/2026) from invoice date",
    "second_q": "Q2/YYYY",
    "third_q": "Q3/YYYY",
    "fourth_q": "Q4/YYYY",
    "invoice_date": "Date of the invoice",
    "n_invoiced": "Number of times this item has been invoiced",
    "invoice_index": "1-based index of this line in current invoice",
    "partner": "Customer (res.partner)",
    "product": "Product (product.product)",
    "quantity": "Quantity for this line",
    "invoiceset_code": "Code of the invoice set",
    "groupvalue": "Value of the grouping field (e.g. lot name)",
}


def _quarter_labels_from_date(env, dt, lang=None):
    """Return dict first_q, second_q, third_q, fourth_q for a date's year.
    Uses translations from locale when lang is set (e.g. Q1→T1 in Spanish)."""

    def _tr(env, lang, src):
        """Get translated string for lang, or return src."""
        if not lang or not env:
            return src
        try:
            trans = env["ir.translation"].search(
                [
                    ("type", "=", "code"),
                    ("lang", "=", lang),
                    ("src", "=", src),
                ],
                limit=1,
            )
            return trans.value if trans and trans.value else src
        except (ValueError, KeyError, AttributeError):
            return src

    if not dt:
        today = date.today()
        year = today.year
    else:
        year = dt.year if hasattr(dt, "year") else int(str(dt)[:4])

    # Format strings for extraction (Q1/%s etc.) - use env._ so lang is from env
    srcs = [env._("Q1/%s"), env._("Q2/%s"), env._("Q3/%s"), env._("Q4/%s")]
    fmts = [_tr(env, lang, s) for s in srcs]
    return {
        "first_q": fmts[0] % year,
        "second_q": fmts[1] % year,
        "third_q": fmts[2] % year,
        "fourth_q": fmts[3] % year,
    }


class ProductCategory(models.Model):
    _inherit = "product.category"

    category_code = fields.Integer(
        default=0,
        required=True,
        readonly=True,
        index=True,
    )

    billable_item_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Billable items model",
        domain=lambda self: self._get_billable_item_model_domain(),
        tracking=True,
    )
    billable_item_model_name = fields.Char(
        related="billable_item_model_id.model",
        string="Billable model technical name",
        readonly=True,
    )

    billable_item_quantity_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Quantity Field",
        domain="[('model_id', '=', billable_item_model_id),"
        " ('ttype', 'in', ('integer', 'float'))]",
        ondelete="set null",
        tracking=True,
    )
    billable_item_quantity_label = fields.Char(
        string="Label of the quantity field",
        translate=True,
        tracking=True,
    )
    billable_item_quantity_ratio = fields.Float(
        string="Quantity ratio",
        default=1.0,
        help="Multiplier applied to the quantity when creating selectable items.",
        tracking=True,
    )

    billable_item_group_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Field for grouping",
        domain="[('model_id', '=', billable_item_model_id),"
        " ('ttype', 'in', ('boolean', 'char', 'date',"
        " 'selection', 'many2one'))]",
        ondelete="set null",
        tracking=True,
    )
    billable_item_group_label = fields.Char(
        string="Label of the grouping field",
        translate=True,
        tracking=True,
    )
    billable_item_detail_desc = fields.Char(
        string="Template for invoice lines",
        translate=True,
        tracking=True,
    )
    billable_item_domain = fields.Char(
        string="Pre-filter on billable items",
        help="Domain applied to billable items before selection."
        " Use the standard domain editor.",
        tracking=True,
    )

    supports_mass_billing = fields.Boolean(
        string="Supports massive billing",
        compute="_compute_supports_mass_billing",
        store=True,
    )

    invoiceset_count = fields.Integer(
        string="Invoice Sets Count",
        compute="_compute_invoiceset_count",
    )
    invoice_line_count = fields.Integer(
        string="Invoice Lines Count",
        compute="_compute_invoice_line_count",
    )
    selectable_item_count = fields.Integer(
        string="Selectable Items Count",
        compute="_compute_selectable_item_count",
    )

    # Auxiliary fields: list of ir.model.fields to show in selectable items
    aux_field_ids = fields.One2many(
        comodel_name="product.category.aux.field.line",
        inverse_name="category_id",
        string="Auxiliary fields",
        copy=True,
    )
    tax_ids = fields.Many2many(
        comodel_name="account.tax",
        relation="product_category_account_tax_rel",
        column1="category_id",
        column2="tax_id",
        string="Customer Taxes (override)",
        domain="[('type_tax_use', '=', 'sale')]",
        help="Optional. If set, these taxes are applied to invoice"
        " lines instead of the product's taxes.",
    )
    # Map billable item fields -> account.move.line fields
    # (e.g. analytic_account_id, ter_parcel_id)
    move_line_field_map_ids = fields.One2many(
        comodel_name="product.category.invoice.line.field.map",
        inverse_name="category_id",
        string="Invoice Line Field Mapping",
        copy=True,
        help="When creating invoice lines, values from the billable record are copied "
        "to these account.move.line fields (e.g. analytic account, parcel reference).",
    )
    aux_desc = fields.Char(string="Wildcard Template", translate=True, tracking=True)
    jinja2_shortcuts_help = fields.Html(
        compute="_compute_jinja2_shortcuts_help",
        string="Template variables",
    )

    _sql_constraints = [
        (
            "category_code_ok",
            "CHECK (category_code >= 0)",
            'Incorrect value for "Category Code".',
        ),
    ]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @api.model
    def get_jinja2_template_context(self, billable_item, **kwargs):
        """Build context dict for Jinja2 templates.

        Used by billable_item_detail_desc and aux_desc rendering.

        Args:
            billable_item: recordset of the billable item
            **kwargs: invoiceset, productlink, product, partner, quantity,
                      invoice_index, groupvalue.
        """
        invoiceset = kwargs.get("invoiceset")
        partner = kwargs.get("partner")
        ctx = {"billable_item": billable_item}
        dt = invoiceset.invoice_date if invoiceset else None
        lang = partner.lang if partner else None
        ctx.update(_quarter_labels_from_date(self.env, dt, lang=lang))
        ctx["invoice_date"] = dt
        ctx["groupvalue"] = kwargs.get("groupvalue") or ""
        if kwargs.get("product"):
            ctx["product"] = kwargs["product"]
        if partner:
            ctx["partner"] = partner
        if kwargs.get("quantity") is not None:
            ctx["quantity"] = kwargs["quantity"]
        if invoiceset:
            ctx["invoiceset_code"] = invoiceset.alphanum_code or ""
        if kwargs.get("invoice_index") is not None:
            ctx["invoice_index"] = kwargs["invoice_index"]
        # n_invoiced: count of invoice lines for this billable item
        if billable_item:
            count = self.env["account.move.line"].search_count(
                [
                    ("billable_item_model", "=", billable_item._name),
                    ("billable_item_res_id", "=", billable_item.id),
                ]
            )
            ctx["n_invoiced"] = count
        return ctx

    @api.model
    def _get_billable_item_model_domain(self):
        """Models that have a Many2one to res.partner (eligible for billable items)."""
        model_recs = self.env["common.metadata"].get_models_with_many2one(
            "res.partner",
            many2one_name="",  # any Many2one to res.partner
            include_model=True,
            exclude_transient=True,
        )
        ids = model_recs.ids
        return [("id", "in", ids)] if ids else [("id", "=", 0)]

    def _get_field_label(self, model_name, field_name):
        if not model_name or not field_name:
            return False
        field = self.env["common.metadata"].get_field(model_name, field_name)
        return field.get("field_description") if field else False

    def _sanitize_vals(self, vals):
        if vals.get("billable_item_model_id") is False:
            reset_fields = [
                "billable_item_quantity_field_id",
                "billable_item_quantity_label",
                "billable_item_quantity_ratio",
                "billable_item_group_field_id",
                "billable_item_group_label",
                "billable_item_detail_desc",
                "billable_item_domain",
                "aux_field_ids",
                "move_line_field_map_ids",
            ]
            for field_name in reset_fields:
                if field_name in ("aux_field_ids", "move_line_field_map_ids"):
                    vals[field_name] = [(5, 0, 0)]
                else:
                    vals[field_name] = False
        return vals

    def _get_domain_field_names(self, domain_str):
        """Extract field names from domain string [('field','op',val), ...]."""
        if not domain_str or not domain_str.strip():
            return []
        try:
            domain = safe_eval(domain_str, {})
            if not isinstance(domain, list):
                return []
            return list(
                dict.fromkeys(
                    item[0]
                    for item in domain
                    if isinstance(item, (list, tuple))
                    and len(item) >= 1
                    and isinstance(item[0], str)
                )
            )
        except (ValueError, SyntaxError):
            return []

    def _ensure_billable_model_indexes(
        self, category
    ):  # noqa: C901  # pylint: disable=R0912,R0914,R0915
        """
        Ensure indexes exist on the billable model table for fields used in
        search, grouping and domain. Improves invoice generation performance.
        """
        if not category or not category.billable_item_model_id:
            return
        model_name = category.billable_item_model_id.sudo().model
        try:
            model = self.env[model_name]
        except KeyError:
            _logger.debug(
                "[base_invoicing] Model %s not found, skipping index check",
                model_name,
            )
            return
        table = getattr(model, "_table", None)
        if not table:
            _logger.debug(
                "[base_invoicing] Model %s has no table, skipping indexes",
                model_name,
            )
            return
        cr = self.env.cr
        # (col_name, field) for type-aware index creation
        to_index = []

        def add_col(fname):
            if not fname:
                return
            field = model._fields.get(fname)
            if not field:
                return
            col = getattr(field, "column", None)
            if col is None:
                col = field.name
            elif isinstance(col, (list, tuple)):
                col = col[0] if col else field.name
            col = col or field.name
            to_index.append((col, field))

        # Partner field (critical for search/grouping) - always index
        partner_name = getattr(model, "_billing_partner_id_name", None) or "partner_id"
        add_col(partner_name)

        # Quantity, group, domain and aux fields
        if category.billable_item_quantity_field_id:
            add_col(category.billable_item_quantity_field_id.name)
        if category.billable_item_group_field_id:
            add_col(category.billable_item_group_field_id.name)
        for fname in self._get_domain_field_names(category.billable_item_domain):
            add_col(fname)
        for line in category.aux_field_ids or []:
            if line.field_id:
                add_col(line.field_id.name)

        seen = set()
        for col, field in to_index:
            if not col or col in seen:
                continue
            seen.add(col)
            try:
                with cr.savepoint():
                    cr.execute(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='public' "
                        "AND table_name=%s AND column_name=%s",
                        (table, col),
                    )
                    if not cr.fetchone():
                        continue
                    cr.execute(
                        "SELECT 1 FROM pg_indexes WHERE schemaname='public' "
                        "AND tablename=%s AND indexdef ILIKE %s",
                        (table, f"%{col}%"),
                    )
                    if cr.fetchone():
                        continue
                    idx_name = f"base_invoicing_idx_{table}_{col}"[:63]
                    # Type-aware index: Many2one/Int/Date/Datetime -> B-tree;
                    # Char -> varchar_pattern_ops; Text -> text_pattern_ops
                    ftype = getattr(field, "type", None) or ""
                    if ftype == "char":
                        cr.execute(  # pylint: disable=E8103
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" '
                            f'("{col}" varchar_pattern_ops)'
                        )
                    elif ftype == "text":
                        cr.execute(  # pylint: disable=E8103
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" '
                            f'("{col}" text_pattern_ops)'
                        )
                    else:
                        # many2one, integer, float, date, datetime, boolean
                        cr.execute(  # pylint: disable=E8103
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}"'
                            f' ON "{table}" ("{col}")'
                        )
                    _logger.info(
                        "[base_invoicing] Created index %s on %s(%s) type=%s",
                        idx_name,
                        table,
                        col,
                        ftype,
                    )
            except Exception as err:  # pylint: disable=W0718
                _logger.warning(
                    "[base_invoicing] Could not create index on %s.%s: %s",
                    table,
                    col,
                    err,
                )

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.onchange("billable_item_model_id", "billable_item_group_field_id")
    def _onchange_billable_item_group_field_id(self):
        """Set label from field metadata; clear field if model changed."""
        if self.billable_item_group_field_id:
            if (
                self.billable_item_model_id
                and self.billable_item_group_field_id.model_id
                != self.billable_item_model_id
            ):
                self.billable_item_group_field_id = False
                self.billable_item_group_label = False
            else:
                self.billable_item_group_label = (
                    self.billable_item_group_field_id.field_description or ""
                )
        else:
            self.billable_item_group_label = False

    @api.onchange("billable_item_model_id", "billable_item_quantity_field_id")
    def _onchange_billable_item_quantity_field_id(self):
        """Set label from field metadata; clear field if model changed."""
        if self.billable_item_quantity_field_id:
            if (
                self.billable_item_model_id
                and self.billable_item_quantity_field_id.model_id
                != self.billable_item_model_id
            ):
                self.billable_item_quantity_field_id = False
                self.billable_item_quantity_label = False
            else:
                self.billable_item_quantity_label = (
                    self.billable_item_quantity_field_id.field_description or ""
                )
        else:
            self.billable_item_quantity_label = False

    def _humanize_template_error(self, err_msg):
        """Convert technical Jinja2/AttributeError to a user-friendly message."""
        # "'...' object has no attribute 'xxx'" -> attribute 'xxx' does not exist
        match = re.search(r"has no attribute ['\"]([^'\"]+)['\"]", str(err_msg))
        if match:
            attr = match.group(1)
            model_name = (
                self.billable_item_model_id.name
                if self.billable_item_model_id
                else "billable_item"
            )
            return self.env._(
                "The attribute '%(attr)s' does not exist in the "
                "billable item model (%(model)s).",
                attr=attr,
                model=model_name,
            )
        # "UndefinedError: 'xxx' is undefined"
        match = re.search(r"['\"]([^'\"]+)['\"] (?:is )?undefined", str(err_msg), re.I)
        if match:
            return self.env._(
                "The variable or attribute '%s' is not defined.", match.group(1)
            )
        return str(err_msg)

    def _validate_jinja2_template(
        self, template_str, lang_code=None
    ):  # pylint: disable=W0613
        """Validate Jinja2 template. Returns (True, None) or (False, error_msg).
        Uses StrictUndefined to catch non-existent attributes (e.g. billable_item.asx).
        """
        if not template_str or not template_str.strip():
            return True, None
        env = Environment(undefined=StrictUndefined)
        try:
            template = env.from_string(template_str)
        except TemplateError as err:
            return False, self._humanize_template_error(err)
        # Try render with mock context (all template variables)
        try:
            if self.billable_item_model_id:
                mock_item = self.env[self.billable_item_model_id.model].new({})
            else:
                mock_item = type(
                    "Mock",
                    (),
                    {
                        "id": 0,
                        "name": "",
                        "display_name": "",
                        "_name": "mock.billable.item",
                        "__str__": lambda s: "",
                    },
                )()
            mock_ctx = self.get_jinja2_template_context(mock_item, quantity=0)
            template.render(**mock_ctx)
        except TemplateError as err:
            return False, self._humanize_template_error(err)
        except Exception as err:  # pylint: disable=W0718
            return False, self._humanize_template_error(err)
        return True, None

    @api.depends()
    def _compute_jinja2_shortcuts_help(self):
        for _rec in self:
            rows = "".join(
                f"<tr><td><code>{{{{ {k} }}}}</code></td>" f"<td>{v}</td></tr>"
                for k, v in JINJA2_TEMPLATE_SHORTCUTS.items()
            )
            self.jinja2_shortcuts_help = (
                f'<div class="alert alert-info mb-0">'
                f'<strong>{self.env._("Jinja2 template variables")}</strong>'
                f'<table class="table table-sm table-borderless mt-2 mb-0">'
                f"{rows}"
                f"</table></div>"
            )

    @api.onchange("billable_item_detail_desc")
    def _onchange_billable_item_detail_desc(self):
        """Validate Jinja2 template on change."""
        if not self.billable_item_detail_desc:
            return None
        ok, err = self._validate_jinja2_template(self.billable_item_detail_desc)
        if not ok:
            return {
                "warning": {
                    "title": self.env._("Invalid template"),
                    "message": self.env._("Template error: %s", err),
                }
            }
        return None

    @api.onchange("aux_desc")
    def _onchange_aux_desc(self):
        """Validate Jinja2 template for selection lines."""
        if not self.aux_desc:
            return None
        ok, err = self._validate_jinja2_template(self.aux_desc)
        if not ok:
            return {
                "warning": {
                    "title": self.env._("Invalid template"),
                    "message": self.env._("Template error: %s", err),
                }
            }
        return None

    def _sync_billable_item_quantity_label_translations(self):
        """Copy translations from ir.model.fields.field_description to label."""
        for record in self:
            if not record.billable_item_quantity_field_id:
                continue
            field = record.billable_item_quantity_field_id
            desc_field = field._fields.get("field_description")
            if not desc_field or not desc_field.translate:
                continue
            translations = desc_field._get_stored_translations(field)
            if not translations:
                continue
            record.update_field_translations(
                "billable_item_quantity_label", translations
            )

    def _sync_billable_item_group_label_translations(self):
        """Copy translations from ir.model.fields.field_description to label."""
        for record in self:
            if not record.billable_item_group_field_id:
                continue
            field = record.billable_item_group_field_id
            desc_field = field._fields.get("field_description")
            if not desc_field or not desc_field.translate:
                continue
            translations = desc_field._get_stored_translations(field)
            if not translations:
                continue
            record.update_field_translations("billable_item_group_label", translations)

    @api.depends("billable_item_model_id")
    def _compute_supports_mass_billing(self):
        for record in self:
            record.supports_mass_billing = bool(record.billable_item_model_id)

    def _compute_invoiceset_count(self):
        for record in self:
            record.invoiceset_count = self.env["account.invoiceset"].search_count(
                [
                    (
                        "productlink_ids.product_id.product_tmpl_id.categ_id",
                        "=",
                        record.id,
                    )
                ]
            )

    def _compute_invoice_line_count(self):
        data = self.env["account.move.line"].read_group(
            [("categ_id", "in", self.ids), ("invoiceset_id", "!=", False)],
            ["categ_id"],
            ["categ_id"],
        )
        mapped = {d["categ_id"][0]: d["categ_id_count"] for d in data if d["categ_id"]}
        for record in self:
            record.invoice_line_count = mapped.get(record.id, 0)

    def _compute_selectable_item_count(self):
        for record in self:
            record.selectable_item_count = self.env[
                "account.selectable.item"
            ].search_count(
                [
                    (
                        "productlink_id.product_id.product_tmpl_id.categ_id",
                        "=",
                        record.id,
                    )
                ]
            )

    # -------------------------------------------------------------------------
    # Display (Odoo 18: avoid name_get)
    # -------------------------------------------------------------------------

    @api.depends("name", "category_code")
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get("short_name_categories"):
            for record in self:
                if record.category_code:
                    record.display_name = (
                        f"{record.name} "
                        f"({record.env._('cat. #')}{record.category_code})"
                    )
                else:
                    record.display_name = record.name
            return

        for record in self:
            if record.category_code <= 0:
                continue
            suffix = (
                record.env._("standard cat.")
                if record.category_code == 1
                else f"{record.env._('cat. #')}{record.category_code}"
            )
            record.display_name = f"{record.display_name} ({suffix})"

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------

    @api.constrains("category_code")
    def _check_category_code(self):
        for record in self:
            if record.category_code <= 0:
                continue
            if self.search_count([("category_code", "=", record.category_code)]) > 1:
                raise ValidationError(record.env._("Repeated category code."))

    @api.constrains("billable_item_detail_desc")
    def _check_billable_item_detail_desc_template(self):
        """Validate Jinja2 template in all languages before save."""
        for record in self:
            if not record.billable_item_detail_desc:
                continue
            field = record._fields["billable_item_detail_desc"]
            translations = field._get_stored_translations(record)
            to_validate = []
            if translations and isinstance(translations, dict):
                for lang_code, value in translations.items():
                    if value and isinstance(value, str):
                        to_validate.append((lang_code, value))
            if not to_validate:
                to_validate = [("", record.billable_item_detail_desc)]
            for lang_code, value in to_validate:
                if not value or not value.strip():
                    continue
                ok, err = record._validate_jinja2_template(value, lang_code)
                if not ok:
                    lang_label = next(
                        (
                            name
                            for code, name in self.env["res.lang"].get_installed()
                            if lang_code in (code, f"_{code}")
                        ),
                        lang_code or self.env.lang,
                    )
                    raise ValidationError(
                        record.env._(
                            "Template for invoice lines [%(lang)s]: %(err)s",
                            lang=lang_label,
                            err=err,
                        )
                    )

    @api.constrains("aux_desc")
    def _check_aux_desc_template(self):
        """Validate Jinja2 aux_desc template in all languages before save."""
        for record in self:
            if not record.aux_desc:
                continue
            field = record._fields["aux_desc"]
            translations = field._get_stored_translations(record)
            to_validate = []
            if translations and isinstance(translations, dict):
                for lang_code, value in translations.items():
                    if value and isinstance(value, str):
                        to_validate.append((lang_code, value))
            if not to_validate:
                to_validate = [("", record.aux_desc)]
            for lang_code, value in to_validate:
                if not value or not value.strip():
                    continue
                ok, err = record._validate_jinja2_template(value, lang_code)
                if not ok:
                    lang_label = next(
                        (
                            name
                            for code, name in self.env["res.lang"].get_installed()
                            if lang_code in (code, f"_{code}")
                        ),
                        lang_code or self.env.lang,
                    )
                    raise ValidationError(
                        record.env._(
                            "Template for selection lines [%(lang)s]: %(err)s",
                            lang=lang_label,
                            err=err,
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sanitize_vals(vals)
        records = super().create(vals_list)
        for record in records.filtered("billable_item_quantity_field_id"):
            record._sync_billable_item_quantity_label_translations()
        for record in records.filtered("billable_item_group_field_id"):
            record._sync_billable_item_group_label_translations()
        for record in records.filtered("billable_item_model_id"):
            record._ensure_billable_model_indexes(record)
        return records

    def write(self, vals):
        self._sanitize_vals(vals)
        has_qty_field = bool(vals.get("billable_item_quantity_field_id"))
        has_group_field = bool(vals.get("billable_item_group_field_id"))
        billable_config = bool(
            vals.get("billable_item_model_id")
            or vals.get("billable_item_quantity_field_id")
            or vals.get("billable_item_group_field_id")
            or vals.get("billable_item_domain")
            or vals.get("aux_field_ids")
        )
        result = super().write(vals)
        if has_qty_field:
            self._sync_billable_item_quantity_label_translations()
        if has_group_field:
            self._sync_billable_item_group_label_translations()
        if billable_config:
            for record in self.filtered("billable_item_model_id"):
                record._ensure_billable_model_indexes(record)
        return result

    def copy(self, default=None):
        default = dict(default or {})
        default["category_code"] = 0
        return super().copy(default)

    def unlink(self):
        for record in self:
            if record.category_code > 0:
                raise UserError(
                    record.env._("It is not possible to delete a coded category.")
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_view_invoicesets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoice Sets"),
            "res_model": "account.invoiceset",
            "view_mode": "list,form",
            "domain": [
                (
                    "productlink_ids.product_id.product_tmpl_id.categ_id",
                    "=",
                    self.id,
                )
            ],
            "context": {"create": False},
        }

    def action_view_invoice_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoice Lines"),
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [
                ("categ_id", "=", self.id),
                ("invoiceset_id", "!=", False),
            ],
            "context": {
                "create": False,
                "search_default_grouped_by_invoiceset_id": 1,
            },
        }

    def action_view_selectable_items(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Selectable Items"),
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "domain": [
                (
                    "productlink_id.product_id.product_tmpl_id.categ_id",
                    "=",
                    self.id,
                )
            ],
            "context": {"create": False, "selectable_items_categ_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Validation helper
    # -------------------------------------------------------------------------

    @api.model
    def _check_field(self, model_name, field_name, admissible_types):
        field = self.env["common.metadata"].get_field(model_name, field_name)
        if not field:
            return False
        allowed = {
            t.strip() for t in (admissible_types or "").lower().split(",") if t.strip()
        }
        return field.get("ttype") in allowed
