# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=translation-not-lazy

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductCategoryInvoiceLineFieldMap(models.Model):
    """
    Maps billable item fields or fixed records to account.move.line fields.
    When creating invoice lines, values are taken from the billable record
    and/or a default record, and copied to the corresponding move line fields.
    """

    _name = "product.category.invoice.line.field.map"
    _description = "Invoice Line Field Mapping (Billable → account.move.line)"
    _order = "sequence, id"

    VALUE_SOURCE_SELECTION = [
        ("from_billable", "From billable field"),
        ("fixed", "Fixed record (default)"),
        ("billable_or_fixed", "Billable field, or fixed if empty"),
    ]

    category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product Category",
        required=True,
        ondelete="cascade",
        index=True,
    )
    billable_model_id = fields.Many2one(
        related="category_id.billable_item_model_id",
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    value_source = fields.Selection(
        selection=VALUE_SOURCE_SELECTION,
        string="Value source",
        default="from_billable",
        required=True,
        help="Where to get the value: from the billable record's field, "
        "from a fixed record (default), or billable with fallback to fixed.",
    )
    move_line_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Invoice Line Field",
        required=True,
        ondelete="cascade",
        domain="[('model', '=', 'account.move.line'), "
        "('ttype', 'not in', ['one2many', 'many2many', 'binary', 'properties']), "
        "('name', 'not in', ['create_uid', 'create_date', 'write_uid', 'write_date'])]",
    )
    compatible_billable_field_ids = fields.Many2many(
        comodel_name="ir.model.fields",
        relation="product_category_invoice_line_field_map_compatible_fields_rel",
        string="Compatible billable fields",
        help="Technical: updated by onchange when move_line_field_id changes. Used for domain.",
    )
    billable_item_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Billable Item Field",
        ondelete="cascade",
        domain="[('id', 'in', compatible_billable_field_ids)]",
        help="Only fields compatible with the invoice line field are shown (e.g. Many2one→Many2one same relation).",
    )
    default_record_ref = fields.Reference(
        selection="_selection_default_record_models",
        string="Default record",
        help="Fixed record for many2one/analytic fields when value source is 'Fixed'. "
        "Must match the invoice line field's model (e.g. analytic account for analytic_distribution).",
    )
    fixed_value = fields.Char(
        string="Fixed value",
        help="Fixed value for selection/char/text/integer/etc when value source is 'Fixed'. "
        "For selection: enter the key (e.g. 'asset_receivable'). For char/text: the string.",
    )
    move_line_field_ttype = fields.Selection(
        related="move_line_field_id.ttype",
        string="Move line field type",
        readonly=True,
    )
    move_line_expects_record = fields.Boolean(
        compute="_compute_move_line_expects_record",
        string="Expects record",
        help="Technical: True if move_line_field is many2one or analytic_distribution.",
    )

    @api.depends(
        "move_line_field_id", "move_line_field_id.ttype", "move_line_field_id.name"
    )
    def _compute_move_line_expects_record(self):
        for rec in self:
            rec.move_line_expects_record = rec._move_line_field_expects_record()

    @api.model
    def _selection_default_record_models(self):
        """Models valid as default records. When move_line_field_id is set, restrict to that field's model."""
        IrModel = self.env["ir.model"]
        IrModelFields = self.env["ir.model.fields"]
        relations = None
        if len(self) == 1 and self.move_line_field_id:
            ml = self.move_line_field_id
            if ml.name == "analytic_distribution":
                relations = ["account.analytic.account"]
            elif ml.ttype == "many2one" and ml.relation and self.env.get(ml.relation):
                relations = [ml.relation]
        if not relations:
            domain = [
                ("model", "=", "account.move.line"),
                ("ttype", "=", "many2one"),
            ]
            relations = IrModelFields.search(domain).mapped("relation") + [
                "account.analytic.account"
            ]
            relations = sorted(set(r for r in relations if r and self.env.get(r)))
        model_recs = IrModel.search([("model", "in", relations)], order="name")
        return [(m.model, m.name) for m in model_recs]

    def _update_compatible_billable_field_ids(self):
        """Set compatible_billable_field_ids from domain (called by onchange so client receives updated value)."""
        IrModelFields = self.env["ir.model.fields"]
        if self.value_source == "fixed":
            self.compatible_billable_field_ids = IrModelFields
        else:
            domain = self._get_billable_field_compatible_domain()
            self.compatible_billable_field_ids = IrModelFields.search(domain)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._update_compatible_billable_field_ids()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(
            k in vals for k in ("move_line_field_id", "value_source", "category_id")
        ):
            for rec in self:
                rec._update_compatible_billable_field_ids()
        return res

    @api.onchange("category_id", "category_id.billable_item_model_id")
    def _onchange_category_clear_fields(self):
        """Clear fields when category or its billable model changes."""
        if self.category_id and self.category_id.billable_item_model_id:
            if (
                self.billable_item_field_id
                and self.billable_item_field_id.model_id
                != self.category_id.billable_item_model_id
            ):
                self.billable_item_field_id = False
        else:
            self.move_line_field_id = False
            self.billable_item_field_id = False
        self._update_compatible_billable_field_ids()

    def _move_line_field_expects_record(self):
        """True if move_line_field expects a record (many2one/analytic), else expects a simple value."""
        self.ensure_one()
        ml = self.move_line_field_id
        if not ml:
            return False
        return ml.ttype == "many2one" or ml.name == "analytic_distribution"

    def _parse_fixed_value(self, ml_field, raw):
        """Parse fixed_value string into the type expected by ml_field."""
        if not raw or not raw.strip():
            return None
        raw = raw.strip()
        ttype = ml_field.ttype
        result = raw
        if ttype in ("char", "text", "selection"):
            result = raw
        elif ttype == "integer":
            try:
                result = int(float(raw))
            except (ValueError, TypeError):
                result = None
        elif ttype == "float":
            try:
                result = float(raw)
            except (ValueError, TypeError):
                result = None
        elif ttype == "boolean":
            result = raw.lower() in ("1", "true", "yes", "t", "y")
        elif ttype == "date":
            result = fields.Date.from_string(raw) if raw else None
        elif ttype == "datetime":
            result = fields.Datetime.from_string(raw) if raw else None
        return result

    @api.onchange("value_source")
    def _onchange_value_source(self):
        """Clear irrelevant fields when value source changes."""
        if self.value_source == "fixed":
            self.billable_item_field_id = False
        elif self.value_source == "from_billable":
            self.default_record_ref = False
            self.fixed_value = False
        self._update_compatible_billable_field_ids()

    def _get_billable_field_compatible_domain(self):
        """Return domain for billable_item_field_id so only compatible fields are shown."""
        if not self.billable_model_id:
            return [("id", "=", 0)]
        base = [("model_id", "=", self.billable_model_id.id)]
        base.append(
            ("ttype", "not in", ["one2many", "many2many", "binary", "properties"])
        )
        if not self.move_line_field_id:
            return base
        ml = self.move_line_field_id
        ml_ttype = ml.ttype

        if ml_ttype in (
            "char",
            "text",
            "integer",
            "float",
            "boolean",
            "date",
            "datetime",
            "selection",
        ):
            base.append(("ttype", "=", ml_ttype))
        elif ml.name == "analytic_distribution":
            base.append(("ttype", "=", "many2one"))
            base.append(("relation", "=", "account.analytic.account"))
        elif ml_ttype == "many2one" and ml.relation:
            base.append(("ttype", "=", "many2one"))
            base.append(("relation", "=", ml.relation))
        return base

    @api.onchange("move_line_field_id")
    def _onchange_move_line_field_id(self):
        """Apply domain to billable field, clear incompatible selections and default_record_ref."""
        if self.default_record_ref and self.move_line_field_id:
            expected = (
                "account.analytic.account"
                if self.move_line_field_id.name == "analytic_distribution"
                else (
                    self.move_line_field_id.relation
                    if self.move_line_field_id.ttype == "many2one"
                    else None
                )
            )
            if expected and str(self.default_record_ref._name) != expected:
                self.default_record_ref = False
        # Clear fixed_value if field now expects a record
        if (
            self.move_line_field_id
            and self._move_line_field_expects_record()
            and self.fixed_value
        ):
            self.fixed_value = False

        self._update_compatible_billable_field_ids()

        if self.billable_item_field_id:
            domain = self._get_billable_field_compatible_domain()
            compatible_ids = self.env["ir.model.fields"].search(domain).ids
            if self.billable_item_field_id.id not in compatible_ids:
                self.billable_item_field_id = False

    @api.constrains(
        "move_line_field_id",
        "billable_item_field_id",
        "category_id",
        "value_source",
        "default_record_ref",
        "fixed_value",
    )
    def _check_field_compatibility(self):  # noqa: C901
        """Ensure field types are compatible for copying."""
        for rec in self:
            if not rec.move_line_field_id or not rec.category_id:
                continue
            ml_field = rec.move_line_field_id
            ml_ttype = ml_field.ttype

            # Value source requirements
            if rec.value_source == "fixed":
                expects_record = rec._move_line_field_expects_record()
                if expects_record:
                    if not rec.default_record_ref:
                        raise ValidationError(
                            _(
                                "When value source is 'Fixed' and invoice line field is Many2one, a default record must be set."
                            )
                        )
                    rec._check_default_record_model(ml_field)
                else:
                    if not rec.fixed_value or not rec.fixed_value.strip():
                        raise ValidationError(
                            _(
                                "When value source is 'Fixed' and invoice line field is Selection/Char/etc, a fixed value must be set."
                            )
                        )
                continue
            if rec.value_source == "from_billable" and not rec.billable_item_field_id:
                raise ValidationError(
                    _(
                        "When value source is 'From billable field', a billable item field must be set."
                    )
                )
            if rec.value_source == "billable_or_fixed":
                expects_record = rec._move_line_field_expects_record()
                has_fallback = (
                    rec.default_record_ref
                    if expects_record
                    else (rec.fixed_value and rec.fixed_value.strip())
                )
                if not rec.billable_item_field_id and not has_fallback:
                    raise ValidationError(
                        _(
                            "When value source is 'Billable or fixed', set a billable item field and/or a default record/value."
                        )
                    )

            bi_field = rec.billable_item_field_id
            if not bi_field:
                continue
            bi_ttype = bi_field.ttype

            # Same simple type: direct copy (including selection)
            if ml_ttype == bi_ttype and ml_ttype in (
                "char",
                "text",
                "integer",
                "float",
                "boolean",
                "date",
                "datetime",
                "selection",
            ):
                continue

            # Many2one cases
            if ml_ttype == "many2one" and bi_ttype == "many2one":
                if ml_field.relation == bi_field.relation:
                    continue
                # Billable field points to the billable model itself: use record id
                billable_model = rec.category_id.billable_item_model_id.model
                if (
                    ml_field.relation == billable_model
                    and bi_field.relation == billable_model
                ):
                    continue  # Same model, OK
                raise ValidationError(
                    _(
                        "Many2one fields must have the same relation "
                        "(invoice line: %(ml)s → %(ml_rel)s, billable: %(bi)s → %(bi_rel)s)."
                    )
                    % {
                        "ml": ml_field.name,
                        "ml_rel": ml_field.relation,
                        "bi": bi_field.name,
                        "bi_rel": bi_field.relation,
                    }
                )

            # Analytic: billable has analytic_account_id (many2one) → move line has analytic_distribution (json)
            if (
                ml_field.name == "analytic_distribution"
                and bi_ttype == "many2one"
                and bi_field.relation == "account.analytic.account"
            ):
                continue

            if ml_ttype != bi_ttype:
                raise ValidationError(
                    _(
                        "Incompatible field types: invoice line field '%(ml)s' (%(ml_t)s) "
                        "vs billable field '%(bi)s' (%(bi_t)s)."
                    )
                    % {
                        "ml": ml_field.name,
                        "ml_t": ml_ttype,
                        "bi": bi_field.name,
                        "bi_t": bi_ttype,
                    }
                )

            if rec.default_record_ref:
                rec._check_default_record_model(ml_field)

    def _check_default_record_model(self, ml_field):
        """Ensure default_record_ref model matches move line field's expected type."""
        self.ensure_one()
        if not self.default_record_ref:
            return
        ref_model = str(self.default_record_ref._name)
        expected = ml_field.relation if ml_field.ttype == "many2one" else None
        if ml_field.name == "analytic_distribution":
            expected = "account.analytic.account"
        if expected and ref_model != expected:
            raise ValidationError(
                _(
                    "Default record must be of type %(expected)s (matching invoice line field %(field)s), "
                    "got %(got)s."
                )
                % {
                    "expected": expected,
                    "field": ml_field.name,
                    "got": ref_model,
                }
            )
