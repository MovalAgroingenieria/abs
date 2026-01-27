# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

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
        if self.env.context.get("skip_fee_autocreate"):
            return partners

        partners._ensure_default_fee()
        return partners

    def _ensure_default_fee(self):
        """Create a default fee per partner when missing."""
        fee_model = self.env["res.fee"]
        for partner in self:
            if not partner.fee_ids:
                fee_model.create({"partner_id": partner.id})
