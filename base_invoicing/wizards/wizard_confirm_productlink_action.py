# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class WizardConfirmProductlinkAction(models.TransientModel):
    _name = "wizard.confirm.productlink.action"
    _description = "Confirm product-link action"

    confirm_message = fields.Char(
        string="Confirmation Message",
        readonly=True,
    )
    operation = fields.Char(
        string="Operation Type",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.update(
            {
                "confirm_message": self.env.context.get("confirm_message", ""),
                "operation": self.env.context.get("operation", ""),
            }
        )
        return res

    def execute_operation(self):
        self.ensure_one()

        active_id = self.env.context.get("active_id")
        if not active_id or not self.operation:
            return

        productlink = self.env["account.invoiceset.productlink"].browse(active_id)
        if not productlink.exists():
            return

        operations = {
            "refresh_selectable_items": productlink.refresh_selectable_items,
            "delete_selectable_items": productlink.delete_selectable_items,
            "delete": productlink.unlink,
        }

        action = operations.get(self.operation)
        if action:
            action()
