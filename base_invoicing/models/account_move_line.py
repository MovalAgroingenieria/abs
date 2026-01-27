# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from collections import defaultdict

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    invoiceset_id = fields.Many2one(
        comodel_name="account.invoiceset",
        compute="_compute_invoiceset_id",
        store=True,
        index=True,
        string="Invoice Set",
    )
    categ_id = fields.Many2one(
        comodel_name="product.category",
        compute="_compute_categ_id",
        store=True,
    )
    invoice_user_id = fields.Many2one(
        comodel_name="res.users",
        compute="_compute_invoice_user_id",
        store=True,
        string="Sales Person",
    )
    price_taxes = fields.Monetary(
        compute="_compute_price_taxes",
        store=True,
        currency_field="currency_id",
        string="Tax",
    )

    billable_item_model = fields.Char(string="Billable item model: name")
    billable_item_res_id = fields.Many2oneReference(
        model_field="billable_item_model",
        string="Billable item model: reference",
    )

    @api.depends("move_id", "move_id.invoiceset_id")
    def _compute_invoiceset_id(self):
        for line in self:
            line.invoiceset_id = line.move_id.invoiceset_id if line.move_id else False

    @api.depends(
        "product_id",
        "product_id.product_tmpl_id",
        "product_id.product_tmpl_id.categ_id",
    )
    def _compute_categ_id(self):
        for line in self:
            if line.product_id and line.product_id.product_tmpl_id:
                line.categ_id = line.product_id.product_tmpl_id.categ_id
            else:
                line.categ_id = False

    @api.depends("move_id", "move_id.invoice_user_id")
    def _compute_invoice_user_id(self):
        for line in self:
            line.invoice_user_id = (
                line.move_id.invoice_user_id if line.move_id else False
            )

    @api.depends("price_total", "price_subtotal", "credit")
    def _compute_price_taxes(self):
        for line in self:
            # Keep legacy behavior: only meaningful on credit lines
            line.price_taxes = (
                (line.price_total - line.price_subtotal) if line.credit > 0 else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._update_billable_item_invoice_count(delta=1)
        return lines

    def unlink(self):
        billable_lines = self.filtered(
            lambda l: l.billable_item_model and l.billable_item_res_id
        )
        res = super().unlink()
        billable_lines._update_billable_item_invoice_count(delta=-1)
        return res

    def _update_billable_item_invoice_count(self, delta):
        """Update number_of_invoices on billable items in bulk.

        This avoids per-record writes and guarantees non-negative counters.
        """
        if not delta:
            return

        by_model = defaultdict(set)
        for line in self:
            if not line.billable_item_model or not line.billable_item_res_id:
                continue
            by_model[line.billable_item_model].add(line.billable_item_res_id)

        if not by_model:
            return

        billable_item_abstract = self.env["account.billable.item"]
        for model_name, res_ids in by_model.items():
            if not billable_item_abstract.inherits_from_account_billable_item(
                model_name
            ):
                continue

            model = self.env.get(model_name)
            if not model:
                continue

            table = model._table
            ids = sorted(res_ids)
            if not ids:
                continue

            # Bulk SQL update: enforce floor to 0
            self.env.cr.execute(
                f"""
                UPDATE {table}
                SET number_of_invoices = GREATEST(number_of_invoices + %s, 0)
                WHERE id = ANY(%s)
                """,
                (int(delta), ids),
            )
