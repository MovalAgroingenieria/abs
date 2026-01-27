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

    def name_get(self):
        return [(record.id, record.field_description) for record in self]


class WizardSelectField(models.TransientModel):
    _name = "wizard.select.field"
    _description = "Select a billable item field"

    selected_field_id = fields.Many2one(
        comodel_name="field.option",
        string="Selected Field",
        domain="[('wizard_id', '=', id)]",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_id = self.env.context.get("active_id")
        if not active_id:
            return res

        category = self.env["product.category"].browse(active_id)
        if not category.exists() or not category.billable_item_model_id:
            return res

        field_types = self.env.context.get("types", "")
        model_name = category.billable_item_model_id.model

        fields_metadata = self.env["common.metadata"].get_fields(
            model_name, field_types
        )

        wizard = self.create({})

        options = []
        for field in fields_metadata or []:
            options.append(
                (
                    0,
                    0,
                    {
                        "wizard_id": wizard.id,
                        "name": field["name"],
                        "field_description": (
                            f'{field["name"]} ({field["field_description"]})'
                        ),
                    },
                )
            )

        if options:
            wizard.write({"selected_field_id": False})
            wizard.env["field.option"].create(
                [
                    {
                        "wizard_id": wizard.id,
                        "name": field["name"],
                        "field_description": f'{field["name"]} ({field["field_description"]})',
                    }
                    for field in fields_metadata
                ]
            )

        return res

    def set_selected_field(self):
        self.ensure_one()

        active_id = self.env.context.get("active_id")
        destination_field = self.env.context.get("field")
        if not active_id or not destination_field or not self.selected_field_id:
            return

        category = self.env["product.category"].browse(active_id)
        if not category.exists():
            return

        category.write(
            {
                destination_field: self.selected_field_id.name,
            }
        )
