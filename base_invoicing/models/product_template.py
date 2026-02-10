# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    invoice_line_count = fields.Integer(
        string="Invoice Lines Count",
        compute="_compute_invoice_line_count",
    )
    invoice_count = fields.Integer(
        string="Invoices Count",
        compute="_compute_invoice_count",
    )
    selectable_item_count = fields.Integer(
        string="Selectable Items Count",
        compute="_compute_selectable_item_count",
    )

    factor_quantity = fields.Float(
        string="Factor applicable to the quantity of product",
        digits=(32, 4),
        default=1.0,
        required=True,
    )
    link_with_billable_items = fields.Boolean(
        string="Link product with its billable items",
        default=False,
    )
    supports_mass_billing = fields.Boolean(
        string="Supports massive billing",
        related="categ_id.supports_mass_billing",
        store=True,
        readonly=True,
    )

    @api.depends("name", "categ_id", "categ_id.name", "categ_id.supports_mass_billing")
    def _compute_display_name(self):
        result = super()._compute_display_name()
        for record in self.filtered(
            lambda r: r.categ_id and r.categ_id.supports_mass_billing
        ):
            record.display_name = f"[{record.categ_id.name}] {record.display_name}"
        return result

    @api.constrains("factor_quantity")
    def _check_factor_quantity_non_negative(self):
        for rec in self:
            if rec.factor_quantity is not False and rec.factor_quantity < 0:
                raise ValidationError(rec.env._("Factor quantity must be >= 0."))

    def _compute_invoice_line_count(self):
        data = self.env["account.move.line"].read_group(
            [
                ("product_id.product_tmpl_id", "in", self.ids),
                ("invoiceset_id", "!=", False),
            ],
            ["product_id"],
            ["product_id"],
        )
        tmpl_counts = {}
        prod_ids = [d["product_id"][0] for d in data if d.get("product_id")]
        prod_to_tmpl = {
            p.id: p.product_tmpl_id.id
            for p in self.env["product.product"].browse(prod_ids)
        }
        for d in data:
            if d.get("product_id"):
                tmpl_id = prod_to_tmpl.get(d["product_id"][0])
                if tmpl_id:
                    cnt = d.get("product_id_count", d.get("__count", 0))
                    tmpl_counts[tmpl_id] = tmpl_counts.get(tmpl_id, 0) + cnt
        for record in self:
            record.invoice_line_count = tmpl_counts.get(record.id, 0)

    def _compute_invoice_count(self):
        for record in self:
            moves = self.env["account.move"].search(
                [
                    ("invoiceset_id", "!=", False),
                    ("invoice_line_ids.product_id.product_tmpl_id", "=", record.id),
                ]
            )
            record.invoice_count = len(moves)

    def _compute_selectable_item_count(self):
        for record in self:
            record.selectable_item_count = self.env[
                "account.selectable.item"
            ].search_count(
                [("productlink_id.product_id.product_tmpl_id", "=", record.id)]
            )

    def action_view_invoice_lines(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.account_move_line_view_list")
        search_view = self.env.ref("base_invoicing.account_move_line_view_search")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoice Lines"),
            "res_model": "account.move.line",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "domain": [
                ("product_id.product_tmpl_id", "=", self.id),
                ("invoiceset_id", "!=", False),
            ],
            "context": {
                "create": False,
                "search_default_grouped_by_invoiceset_id": 1,
            },
        }

    def action_view_invoices(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "domain": [
                ("invoiceset_id", "!=", False),
                ("invoice_line_ids.product_id.product_tmpl_id", "=", self.id),
            ],
            "context": {"create": False},
        }

    def action_view_selectable_items(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Selectable Items"),
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "domain": [("productlink_id.product_id.product_tmpl_id", "=", self.id)],
            "context": {
                "create": False,
                "selectable_items_categ_id": (
                    self.categ_id.id if self.categ_id else None
                ),
            },
        }
