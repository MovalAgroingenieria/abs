# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    fee_ids = fields.One2many(
        comodel_name="res.fee",
        inverse_name="partner_id",
        string="Associated Fee",
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        fee_model = self.env["res.fee"]

        for partner in partners:
            fee_model.create({"partner_id": partner.id})

        return partners
