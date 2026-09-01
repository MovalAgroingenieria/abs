# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class MetSource(models.AbstractModel):
    _name = "met.source"
    _description = "Measurement Source"
    _inherit = "simple.model"

    magnitude_id = fields.Many2one("uom.category", required=True, index=True)
    default_uom_id = fields.Many2one(
        "uom.uom",
        required=True,
        index=True,
        domain="[('category_id', '=', magnitude_id)]",
    )
    measurement_count = fields.Integer(
        compute="_compute_measurement_count", readonly=True
    )

    @api.depends()
    def _compute_measurement_count(self):
        """Compute number of measurements.
        Uses read_group for efficiency. Subclasses must define
        _measurement_model (str) with the concrete measurement model name.
        """
        for record in self:
            record.measurement_count = 0
