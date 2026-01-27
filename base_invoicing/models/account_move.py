# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    invoiceset_id = fields.Many2one(
        comodel_name="account.invoiceset",
        string="Invoice Set",
        index=True,
        ondelete="restrict",
        copy=False,
        readonly=True,
        check_company=True,
    )
