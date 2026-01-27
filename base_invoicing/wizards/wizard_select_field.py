# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code

from odoo import api, fields, models


class FieldOption(models.TransientModel):
    _name = "field.option"
    _description = "Selectable field option"

    wizard_id = fields.Many2one(
        comodel_name="wizard.select.field",
        ondelete="cascade",
        required=True,
    )
    name = fields.Char(required=True)
    field_description = fields.Char(required=True)

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.field_description or record.name


class WizardSelectField(models.TransientModel):
    _name = "wizard.select.field"
    _description = "Select a billable item field"

    option_ids = fields.One2many(
        comodel_name="field.option",
        inverse_name="wizard_id",
        readonly=True,
    )
    selected_field_id = fields.Many2one(
        comodel_name="field.option",
        string="Selected Field",
        domain="[('wizard_id', '=', id)]",
    )

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)

        active_id = self.env.context.get("active_id")
        if not active_id:
            return res

        category = self.env["product.category"].browse(active_id).exists()
        if not category or not category.billable_item_model_id:
            return res

        field_types = self.env.context.get("types") or ""
        model_name = category.billable_item_model_id.model

        fields_metadata = (
            self.env["common.metadata"].get_fields(model_name, field_types) or []
        )
        option_commands = [
            (
                0,
                0,
                {
                    "name": field_info["name"],
                    "field_description": "%s (%s)"
                    % (field_info["name"], field_info["field_description"]),
                },
            )
            for field_info in fields_metadata
            if field_info.get("name") and field_info.get("field_description")
        ]

        if option_commands:
            res["option_ids"] = option_commands
            res["selected_field_id"] = False

        return res

    def set_selected_field(self):
        self.ensure_one()

        active_id = self.env.context.get("active_id")
        destination_field = self.env.context.get("field")
        if not active_id or not destination_field or not self.selected_field_id:
            return False

        category = self.env["product.category"].browse(active_id).exists()
        if not category:
            return False

        category.write({destination_field: self.selected_field_id.name})
        return True
