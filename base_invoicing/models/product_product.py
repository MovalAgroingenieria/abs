# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.depends("product_tmpl_id", "categ_id", "categ_id.name", "categ_id.supports_mass_billing")
    def _compute_display_name(self):
        super()._compute_display_name()
        for record in self.filtered(
            lambda r: r.categ_id and r.categ_id.supports_mass_billing
        ):
            record.display_name = f"[{record.categ_id.name}] {record.display_name}"

    def action_view_invoices(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_invoices()

    def action_view_invoice_lines(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_invoice_lines()

    def action_view_selectable_items(self):
        self.ensure_one()
        return self.product_tmpl_id.action_view_selectable_items()
