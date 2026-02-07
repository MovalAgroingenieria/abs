# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.sql import SQL


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
        string="Invoice Category",
        help="Product category for invoicing (from product template). "
        "Avoids label clash with account.product_category_id.",
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
            line.categ_id = (
                line.product_id.product_tmpl_id.categ_id
                if line.product_id and line.product_id.product_tmpl_id
                else False
            )

    @api.depends("move_id", "move_id.invoice_user_id")
    def _compute_invoice_user_id(self):
        for line in self:
            line.invoice_user_id = (
                line.move_id.invoice_user_id if line.move_id else False
            )

    @api.depends("price_total", "price_subtotal", "credit")
    def _compute_price_taxes(self):
        for line in self:
            line.price_taxes = (
                (line.price_total - line.price_subtotal) if line.credit > 0 else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._billable_update_invoice_count(delta=1)
        return lines

    def unlink(self):
        lines = self.exists()
        payload = lines._billable_payload()
        res = super(AccountMoveLine, lines).unlink()
        # apply after unlink using payload; never touch `lines` fields again
        self._billable_apply_payload(payload, delta=-1)
        return res

    def _billable_payload(self):
        """Return {model_name: set(res_id)} only with valid refs."""
        payload = defaultdict(set)
        for line in self.exists():
            model_name = line.billable_item_model
            res = line.billable_item_res_id
            if not model_name or not res:
                continue

            # Many2oneReference may be an int or a record (depending on context)
            res_id = res.id if hasattr(res, "id") else int(res)
            payload[model_name].add(res_id)
        return payload

    def _billable_update_invoice_count(self, delta):
        if not delta:
            return
        self._billable_apply_payload(self._billable_payload(), delta=delta)

    def _billable_apply_payload(self, payload, delta):
        """
        Bulk update number_of_invoices for billable items.
        - Only for models inheriting account.billable.item
        - Never below 0
        """
        if not delta or not payload:
            return

        billable_item_obj = self.env["account.billable.item"]

        for model_name, res_ids in payload.items():
            if not res_ids:
                continue
            if not billable_item_obj.inherits_from_account_billable_item(model_name):
                continue

            model = self.env[model_name].sudo()
            field = model._fields.get("number_of_invoices")
            if not field or not field.store:
                continue

            ids = sorted(res_ids)
            query = SQL(
                """
                UPDATE %s
                SET number_of_invoices =
                        GREATEST(COALESCE(number_of_invoices, 0) + %s, 0)
                WHERE id = ANY (%s)
                """,
                SQL.identifier(model._table),
                delta,
                ids,
            )
            self.env.execute_query(query)
            model.browse(ids).invalidate_recordset(["number_of_invoices"])
