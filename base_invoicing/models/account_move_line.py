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
        self = self.exists()
        payload = self._billable_payload()
        res = super().unlink()
        self._billable_apply_payload(payload, delta=-1)
        return res

    def _billable_payload(self):
        """Return {model_name: set(res_id)} only with valid refs."""
        payload = defaultdict(set)
        for line in self:
            if line.billable_item_model and line.billable_item_res_id:
                payload[line.billable_item_model].add(line.billable_item_res_id)
        return payload

    def _billable_update_invoice_count(self, delta):
        payload = self._billable_payload()
        self._billable_apply_payload(payload, delta=delta)

    def _billable_apply_payload(self, payload, delta):
        if not delta or not payload:
            return

        billable_item_model = self.env["account.billable.item"]
        for model_name, res_ids in payload.items():
            if not res_ids:
                continue
            if not billable_item_model.inherits_from_account_billable_item(model_name):
                continue

            records = self.env[model_name].sudo().browse(list(res_ids)).exists()
            if not records:
                continue
            if "number_of_invoices" not in records._fields:
                continue

            for rec in records:
                rec.number_of_invoices = max((rec.number_of_invoices or 0) + delta, 0)

    def _update_billable_item_invoice_count(self, delta):
        """
        if billable_item_model/res_id points to a model inheriting account.billable.item
        then increment/decrement its number_of_invoices, never below 0.
        """
        if not delta:
            return

        billable_item_model_names = set(self.mapped("billable_item_model"))
        billable_item_model_names.discard(False)
        if not billable_item_model_names:
            return

        billable_item_obj = self.env["account.billable.item"]
        valid_models = {
            name
            for name in billable_item_model_names
            if billable_item_obj.inherits_from_account_billable_item(name)
        }
        if not valid_models:
            return

        ids_by_model = {}
        for line in self:
            if line.billable_item_model in valid_models and line.billable_item_res_id:
                ids_by_model.setdefault(line.billable_item_model, set()).add(
                    line.billable_item_res_id
                )

        for model_name, res_ids in ids_by_model.items():
            ids = sorted(res_ids)
            if not ids:
                continue

            model = self.env[model_name].sudo()
            field = model._fields.get("number_of_invoices")
            if not field or not field.store:
                continue

            query = SQL(
                """
                UPDATE %s
                SET number_of_invoices = GREATEST(number_of_invoices + %s, 0)
                WHERE id = ANY (%s)
                """,
                SQL.identifier(model._table),
                delta,
                ids,
            )
            self.env.execute_query(query)
            self._invalidate_cache()
