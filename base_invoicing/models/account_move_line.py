# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = ['account.move.line']

    invoiceset_id = fields.Many2one(
        string='Invoice Set',
        comodel_name='account.invoiceset',
        store=True,
        index=True,
        compute='_compute_invoiceset_id',)

    @api.depends('move_id', 'move_id.invoiceset_id')
    def _compute_invoiceset_id(self):
        for record in self:
            invoiceset_id = None
            if record.move_id and record.move_id.invoiceset_id:
                invoiceset_id = record.move_id.invoiceset_id
            record.invoiceset_id = invoiceset_id
