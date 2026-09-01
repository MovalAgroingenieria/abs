# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class MetDeviceMixin(models.AbstractModel):
    _name = "met.device.mixin"
    _description = "Device Mixin"
    _inherit = "simple.model"

    brand = fields.Char(size=100)
    model_name = fields.Char(size=100)
    serial_number = fields.Char(size=100, index=True)
    device_state = fields.Selection(
        [("active", "Active"), ("archived", "Archived")],
        required=True,
        default="active",
    )
    installation_date = fields.Date()

    _sql_constraints = [
        (
            "serial_number_unique",
            "UNIQUE (serial_number)",
            "Serial number must be unique.",
        ),
    ]
