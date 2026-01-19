# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mass_invoicing_seq_invoiceset_code_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Invoice Set Sequence",
    )

    mass_invoicing_run_background = fields.Boolean(
        string="Run invoice set calculation in background",
        default=False,
    )
