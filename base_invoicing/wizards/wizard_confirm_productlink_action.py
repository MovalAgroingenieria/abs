# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class WizardConfirmProductlinkAction(models.TransientModel):
    _name = "wizard.confirm.productlink.action"
    _description = "Confirm product-link action"

    confirm_message = fields.Char(readonly=True)
    operation = fields.Char(readonly=True)

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        res.update(
            {
                "confirm_message": self.env.context.get("confirm_message") or "",
                "operation": self.env.context.get("operation") or "",
            }
        )
        return res

    def execute_operation(self):
        self.ensure_one()

        active_id = self.env.context.get("active_id")
        if not active_id or not self.operation:
            return False

        productlink = (
            self.env["account.invoiceset.productlink"].browse(active_id).exists()
        )
        if not productlink:
            return False

        operation_map = {
            "refresh_selectable_items": productlink.refresh_selectable_items,
            "delete_selectable_items": productlink.delete_selectable_items,
            "delete": productlink.unlink,
        }
        action = operation_map.get(self.operation)
        if action:
            action()
        return True
