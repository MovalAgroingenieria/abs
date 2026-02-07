# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_view_invoices(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_invoices()

    def action_view_invoice_lines(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_invoice_lines()

    def action_view_selectable_items(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_selectable_items()
