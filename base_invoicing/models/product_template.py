# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = ['product.template']

    factor_quantity = fields.Float(
        string='Factor applicable to the quantity of product',
        digits=(32, 4),
        default=1,
        required=True,)

    supports_mass_billing = fields.Boolean(
        string='Supports massive billing (y/n)',
        related='categ_id.supports_mass_billing',)

    _sql_constraints = [
        ('factor_quantity_ok', 'CHECK (factor_quantity >= 0)',
         'Incorrect value for "Factor applicable to the quantity of product".'),
    ]
