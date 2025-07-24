# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = ['account.move']

    invoiceset_id = fields.Many2one(
        string='Invoice Set',
        comodel_name='account.invoiceset',
        index=True,
        ondelete='restrict',)
