# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mass_invoicing_seq_invoiceset_code_id = fields.Many2one(
        related="company_id.mass_invoicing_seq_invoiceset_code_id",
        readonly=False,
    )

    mass_invoicing_run_background = fields.Boolean(
        related="company_id.mass_invoicing_run_background",
        readonly=False,
    )
