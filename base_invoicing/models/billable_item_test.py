# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class BillableItemTest(models.Model):
    _name = "base_invoicing.billable_item_test"
    _description = "Billable item test model"
    _inherit = "account.billable.item"

    partner_id = fields.Many2one("res.partner")
    quantity = fields.Float(default=1.0)
