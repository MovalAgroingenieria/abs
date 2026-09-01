# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class MetMeasurement(models.AbstractModel):
    _name = "met.measurement"
    _description = "Measurement"
    _order = "timestamp desc"

    timestamp = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    magnitude_id = fields.Many2one("uom.category", required=True, index=True)
    uom_id = fields.Many2one(
        "uom.uom",
        required=True,
        index=True,
        domain="[('category_id', '=', magnitude_id)]",
    )
    value = fields.Float(required=True, digits=(16, 4))
