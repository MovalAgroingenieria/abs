# 2025 Moval Agroingeniería
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
        string="Product Category",
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

    @api.depends("move_id.invoiceset_id")
    def _compute_invoiceset_id(self):
        for line in self:
            line.invoiceset_id = line.move_id.invoiceset_id

    @api.depends("product_id.product_tmpl_id.categ_id")
    def _compute_categ_id(self):
        for line in self:
            line.categ_id = line.product_id.product_tmpl_id.categ_id

    @api.depends("move_id.invoice_user_id")
    def _compute_invoice_user_id(self):
        for line in self:
            line.invoice_user_id = line.move_id.invoice_user_id

    @api.depends("price_total", "price_subtotal", "credit")
    def _compute_price_taxes(self):
        for line in self:
            line.price_taxes = (
                line.price_total - line.price_subtotal if line.credit > 0 else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._update_billable_item_invoice_count(delta=1)
        return lines

    def unlink(self):
        billable_lines = self.filtered(lambda l: l.billable_item_model and l.billable_item_res_id)
        res = super().unlink()
        billable_lines._update_billable_item_invoice_count(delta=-1)
        return res

    def _update_billable_item_invoice_count(self, delta):
        if not delta:
            return

        by_model = defaultdict(list)
        for line in self:
            if not line.billable_item_model or not line.billable_item_res_id:
                continue
            by_model[line.billable_item_model].append(line.billable_item_res_id)

        billable_item_abstract = self.env["account.billable.item"]
        for model_name, res_ids in by_model.items():
            if not billable_item_abstract.inherits_from_account_billable_item(model_name):
                continue
            records = self.env[model_name].sudo().browse(res_ids).exists()
            if not records:
                continue

            if delta > 0:
                for rec in records:
                    rec.write({"number_of_invoices": rec.number_of_invoices + delta})
            else:
                for rec in records:
                    rec.write({"number_of_invoices": max(rec.number_of_invoices + delta, 0)})
