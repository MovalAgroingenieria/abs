# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    factor_quantity = fields.Float(
        string="Factor applicable to the quantity of product",
        digits=(32, 4),
        default=1.0,
        required=True,
    )
    link_with_billable_items = fields.Boolean(
        string="Link product with its billable items",
        default=False,
    )
    supports_mass_billing = fields.Boolean(
        string="Supports massive billing",
        related="categ_id.supports_mass_billing",
        store=True,
        readonly=True,
    )

    @api.constrains("factor_quantity")
    def _check_factor_quantity_non_negative(self):
        for rec in self:
            if rec.factor_quantity is not False and rec.factor_quantity < 0:
                raise ValidationError(rec.env._("Factor quantity must be >= 0."))
