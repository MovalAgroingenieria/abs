# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class ProductCategoryAuxFieldLine(models.Model):
    _name = "product.category.aux.field.line"
    _description = "Auxiliary field definition for selectable items"
    _order = "sequence, id"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("category_id") and self.env.context.get(
                "default_category_id"
            ):
                vals["category_id"] = self.env.context["default_category_id"]
        return super().create(vals_list)

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
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', billable_model_id), "
        "('ttype', 'not in', ['one2many', 'many2many', 'binary', 'properties'])]",
    )
    custom_label = fields.Char(
        string="Label",
        translate=True,
    )

    @api.onchange("category_id", "category_id.billable_item_model_id")
    def _onchange_category_clear_field(self):
        """Clear field_id when category or its billable model changes incompatibly."""
        if (
            self.field_id
            and self.category_id
            and self.category_id.billable_item_model_id
        ):
            if self.field_id.model_id != self.category_id.billable_item_model_id:
                self.field_id = False

    @api.onchange("field_id")
    def _onchange_field_id(self):
        if self.field_id:
            self.custom_label = self.field_id.field_description or self.field_id.name
        else:
            self.custom_label = False
