# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=duplicate-code
# pylint: disable=no-raise-unlink
# pylint: disable=translation-not-lazy
# pylint: disable=translation-positional-used

import re

from jinja2 import Environment, StrictUndefined, Template, TemplateError

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        domain="[('model_id', '=', billable_item_model_id), ('ttype', 'in', ('integer', 'float'))]",
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
        domain="[('model_id', '=', billable_item_model_id), ('ttype', 'in', ('boolean', 'char', 'date', 'selection', 'many2one'))]",
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
        help="Domain applied to billable items before selection. Use the standard domain editor.",
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

    aux_desc = fields.Char(string="Wildcard Template", translate=True, tracking=True)

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
    def _get_billable_item_model_domain(self):
        """Models that have a Many2one to res.partner (eligible for billable items)."""
        models = self.env["common.metadata"].get_models_with_many2one(
            "res.partner",
            many2one_name="",  # any Many2one to res.partner
            include_model=True,
            exclude_transient=True,
        )
        ids = models.ids
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
            ]
            for field_name in reset_fields:
                if field_name == "aux_field_ids":
                    vals[field_name] = [(5, 0, 0)]
                else:
                    vals[field_name] = False
        return vals

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
                "The attribute '%(attr)s' does not exist in the billable item model (%(model)s).",
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

    def _validate_jinja2_template(self, template_str, lang_code=None):
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
        # Try render with mock billable_item
        try:
            if self.billable_item_model_id:
                mock = self.env[self.billable_item_model_id.model].new({})
            else:
                mock = type(
                    "Mock",
                    (),
                    {"id": 0, "name": "", "display_name": "", "__str__": lambda s: ""},
                )()
            template.render(billable_item=mock)
        except TemplateError as err:
            return False, self._humanize_template_error(err)
        except Exception as err:
            return False, self._humanize_template_error(err)
        return True, None

    @api.onchange("billable_item_detail_desc")
    def _onchange_billable_item_detail_desc(self):
        """Validate Jinja2 template on change. Checks current language value."""
        if not self.billable_item_detail_desc:
            return
        ok, err = self._validate_jinja2_template(self.billable_item_detail_desc)
        if not ok:
            return {
                "warning": {
                    "title": self.env._("Invalid template"),
                    "message": self.env._("Template error: %s", err),
                }
            }

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
            record.update_field_translations(
                "billable_item_group_label", translations
            )

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
                            if code == lang_code or f"_{code}" == lang_code
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sanitize_vals(vals)
        records = super().create(vals_list)
        for record in records.filtered("billable_item_quantity_field_id"):
            record._sync_billable_item_quantity_label_translations()
        for record in records.filtered("billable_item_group_field_id"):
            record._sync_billable_item_group_label_translations()
        return records

    def write(self, vals):
        self._sanitize_vals(vals)
        has_qty_field = bool(vals.get("billable_item_quantity_field_id"))
        has_group_field = bool(vals.get("billable_item_group_field_id"))
        result = super().write(vals)
        if has_qty_field:
            self._sync_billable_item_quantity_label_translations()
        if has_group_field:
            self._sync_billable_item_group_label_translations()
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
