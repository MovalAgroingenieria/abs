# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = ['res.partner']

    fee_ids = fields.One2many(
        string='Associated Fee',
        comodel_name='res.fee',
        inverse_name='partner_id',)

    @api.model_create_multi
    def create(self, vals_list):
        partners = super(ResPartner, self).create(vals_list)
        for partner in partners.sudo():
            partner.write({'fee_ids': [(0, 0, {})]})
        return partners
