# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=duplicate-code
# pylint: disable=no-raise-unlink
# pylint: disable=translation-not-lazy
# pylint: disable=translation-positional-used

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
        string="Billable-items Model",
        domain="[('id', 'in', allowed_billable_item_model_ids.ids)]",
    )
    allowed_billable_item_model_ids = fields.Many2many(
        comodel_name="ir.model",
        compute="_compute_allowed_billable_item_model_ids",
        string="Allowed billable models",
    )

    billable_item_quantity_field = fields.Char(string="Quantity Field")
    billable_item_quantity_label = fields.Char(
        string="Label of the quantity field",
        compute="_compute_billable_item_quantity_label",
        store=True,
        readonly=False,
        translate=True,
    )

    billable_item_group_field = fields.Char(string="Field for grouping")
    billable_item_detail_desc = fields.Char(
        string="Template for invoice lines",
        translate=True,
    )
    billable_item_domain = fields.Char(string="Pre-filter on billable items")

    supports_mass_billing = fields.Boolean(
        string="Supports massive billing",
        compute="_compute_supports_mass_billing",
        store=True,
    )

    # Auxiliary fields (definitions only, labels are computed)
    aux_01_char_field = fields.Char(string="Aux. field of type char #1")
    aux_01_char_label = fields.Char(
        string="Label of the aux. field of type char #1",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_01_int_field = fields.Char(string="Aux. field of type integer #1")
    aux_01_int_label = fields.Char(
        string="Label of the aux. field of type integer #1",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_01_float_field = fields.Char(string="Aux. field of type float #1")
    aux_01_float_label = fields.Char(
        string="Label of the aux. field of type float #1",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_01_bool_field = fields.Char(string="Aux. field of type boolean #1")
    aux_01_bool_label = fields.Char(
        string="Label of the aux. field of type boolean #1",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )

    aux_02_char_field = fields.Char(string="Aux. field of type char #2")
    aux_02_char_label = fields.Char(
        string="Label of the aux. field of type char #2",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_02_int_field = fields.Char(string="Aux. field of type integer #2")
    aux_02_int_label = fields.Char(
        string="Label of the aux. field of type integer #2",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_02_float_field = fields.Char(string="Aux. field of type float #2")
    aux_02_float_label = fields.Char(
        string="Label of the aux. field of type float #2",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_02_bool_field = fields.Char(string="Aux. field of type boolean #2")
    aux_02_bool_label = fields.Char(
        string="Label of the aux. field of type boolean #2",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )

    aux_03_char_field = fields.Char(string="Aux. field of type char #3")
    aux_03_char_label = fields.Char(
        string="Label of the aux. field of type char #3",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_03_int_field = fields.Char(string="Aux. field of type integer #3")
    aux_03_int_label = fields.Char(
        string="Label of the aux. field of type integer #3",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_03_float_field = fields.Char(string="Aux. field of type float #3")
    aux_03_float_label = fields.Char(
        string="Label of the aux. field of type float #3",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )
    aux_03_bool_field = fields.Char(string="Aux. field of type boolean #3")
    aux_03_bool_label = fields.Char(
        string="Label of the aux. field of type boolean #3",
        compute="_compute_aux_labels",
        store=True,
        readonly=False,
        translate=True,
    )

    aux_desc = fields.Char(string="Wildcard Template", translate=True)

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

    def _get_field_label(self, model_name, field_name):
        if not model_name or not field_name:
            return False
        field = self.env["common.metadata"].get_field(model_name, field_name)
        return field.get("field_description") if field else False

    def _sanitize_vals(self, vals):
        if vals.get("billable_item_model_id") is False:
            reset_fields = [
                "billable_item_quantity_field",
                "billable_item_quantity_label",
                "billable_item_group_field",
                "billable_item_detail_desc",
                "billable_item_domain",
                "aux_01_char_field",
                "aux_01_char_label",
                "aux_01_int_field",
                "aux_01_int_label",
                "aux_01_float_field",
                "aux_01_float_label",
                "aux_01_bool_field",
                "aux_01_bool_label",
                "aux_02_char_field",
                "aux_02_char_label",
                "aux_02_int_field",
                "aux_02_int_label",
                "aux_02_float_field",
                "aux_02_float_label",
                "aux_02_bool_field",
                "aux_02_bool_label",
                "aux_03_char_field",
                "aux_03_char_label",
                "aux_03_int_field",
                "aux_03_int_label",
                "aux_03_float_field",
                "aux_03_float_label",
                "aux_03_bool_field",
                "aux_03_bool_label",
            ]
            for field_name in reset_fields:
                vals[field_name] = False
        return vals

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends_context("uid")
    def _compute_allowed_billable_item_model_ids(self):
        model_ids = (
            self.env["common.metadata"]
            .get_models_with_many2one(
                "res.partner",
                many2one_name="partner_id",
                include_model=True,
            )
            .ids
        )
        allowed = self.env["ir.model"].browse(model_ids)
        for record in self:
            record.allowed_billable_item_model_ids = allowed

    @api.depends("billable_item_model_id", "billable_item_quantity_field")
    def _compute_billable_item_quantity_label(self):
        for record in self:
            record.billable_item_quantity_label = record._get_field_label(
                record.billable_item_model_id.model,
                record.billable_item_quantity_field,
            )

    @api.depends("billable_item_model_id")
    def _compute_supports_mass_billing(self):
        for record in self:
            record.supports_mass_billing = bool(record.billable_item_model_id)

    @api.depends(
        "billable_item_model_id",
        "aux_01_char_field",
        "aux_01_int_field",
        "aux_01_float_field",
        "aux_01_bool_field",
        "aux_02_char_field",
        "aux_02_int_field",
        "aux_02_float_field",
        "aux_02_bool_field",
        "aux_03_char_field",
        "aux_03_int_field",
        "aux_03_float_field",
        "aux_03_bool_field",
    )
    def _compute_aux_labels(self):
        for record in self:
            model = record.billable_item_model_id.model
            for idx in ("01", "02", "03"):
                for ttype in ("char", "int", "float", "bool"):
                    field_name = f"aux_{idx}_{ttype}_field"
                    label_name = f"aux_{idx}_{ttype}_label"
                    record[label_name] = record._get_field_label(
                        model, record[field_name]
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sanitize_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._sanitize_vals(vals)
        return super().write(vals)

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

    def action_select_billable_item_field(self):
        self.ensure_one()
        if not self.billable_item_model_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Warning"),
                    "message": self.env._(
                        "It is mandatory to set the billable items model."
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Model: %s (%s)")
            % (self.billable_item_model_id.model, self.billable_item_model_id.name),
            "res_model": "wizard.select.field",
            "view_mode": "form",
            "target": "new",
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
