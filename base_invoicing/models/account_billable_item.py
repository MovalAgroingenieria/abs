# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from collections import defaultdict

from odoo import api, fields, models


class AccountBillableItem(models.AbstractModel):
    _name = "account.billable.item"
    _description = "Abstract model for billable records"

    # These names are intended to be overridden at model definition level.
    _billing_partner_id_name = "partner_id"
    _billing_quantity_name = "quantity"
    _billing_groupvalue_name = ""

    billing_partner_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_billing_partner_id",
        string="Billing partner reference",
    )
    billing_quantity = fields.Float(
        compute="_compute_billing_quantity",
        digits=(32, 4),
        string="Billing quantity",
    )
    billing_groupvalue = fields.Char(
        compute="_compute_billing_groupvalue",
        string="Grouping value",
    )
    number_of_invoices = fields.Integer(
        default=0,
        readonly=True,
        string="No. of invoices",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        index=True,
        ondelete="restrict",
    )
    move_line_ids = fields.One2many(
        comodel_name="account.move.line",
        compute="_compute_move_line_ids",
        string="Invoice lines",
    )
    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        string="Invoices",
        copy=False,
        help="Invoices this item was billed in. Stored so consolidated "
        "lines (several items merged into one invoice line) keep the "
        "link to every source item, not just the first one.",
    )
    invoice_count = fields.Integer(
        compute="_compute_invoice_count",
        string="No. of invoices",
    )
    is_invoiced = fields.Boolean(
        compute="_compute_invoice_count",
        string="Invoiced",
    )

    def _compute_billing_partner_id(self):
        for record in self:
            field_name = record._billing_partner_id_name
            record.billing_partner_id = (
                getattr(record, field_name, False) if field_name else False
            )

    def _compute_billing_quantity(self):
        for record in self:
            field_name = record._billing_quantity_name
            record.billing_quantity = (
                getattr(record, field_name, 1.0) if field_name else 1.0
            )

    def _compute_billing_groupvalue(self):
        for record in self:
            field_name = record._billing_groupvalue_name
            value = getattr(record, field_name, False) if field_name else False
            record.billing_groupvalue = "" if value in (False, None) else str(value)

    def _compute_move_line_ids(self):
        """Compute move lines in batch to avoid N+1 queries."""
        if not self:
            return

        domain = [
            ("billable_item_model", "=", self._name),
            ("billable_item_res_id", "in", self.ids),
        ]
        lines = self.env["account.move.line"].search(domain)

        by_res_id = defaultdict(lambda: self.env["account.move.line"])
        for line in lines:
            by_res_id[line.billable_item_res_id] |= line

        for record in self:
            record.move_line_ids = by_res_id.get(
                record.id, self.env["account.move.line"]
            )

    @api.depends("move_line_ids", "invoice_ids", "invoice_ids.state")
    def _compute_invoice_count(self):
        for record in self:
            moves = record._get_active_invoices()
            record.invoice_count = len(moves)
            record.is_invoiced = bool(moves)

    def _get_active_invoices(self):
        """Return non-cancelled invoices linked to this item.

        Combines the forward reference stored on invoice lines
        (``billable_item_res_id``) with the stored ``invoice_ids`` link,
        so both detailed (1:1) and consolidated (n:1) lines are covered.
        """
        self.ensure_one()
        moves = self.move_line_ids.move_id | self.invoice_ids
        return moves.filtered(lambda move: move.state != "cancel")

    def action_view_invoices(self):
        """Open the invoices billed against this billable item."""
        self.ensure_one()
        moves = self._get_active_invoices()
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices"),
            "res_model": "account.move",
            "domain": [("id", "in", moves.ids)],
            "context": {"create": False},
        }
        if len(moves) == 1:
            action["view_mode"] = "form"
            action["res_id"] = moves.id
        else:
            action["view_mode"] = "list,form"
        return action

    # -------------------------------------------------------------------------
    # Helper API (safe, no runtime class mutation)
    # -------------------------------------------------------------------------

    @api.model
    def exists_active_field(self, model_name):
        """Return True if model defines a stored boolean field named 'active'."""
        field_meta = self.env["common.metadata"].get_field(
            model_name,
            "active",
            exclude_related=True,
        )
        return bool(field_meta and field_meta.get("ttype") == "boolean")

    @api.model
    def inherits_from_account_billable_item(self, model_name):
        inherited_models = (
            self.env["common.metadata"].get_inherited_models(model_name) or []
        )
        return self._name in inherited_models

    @api.model
    def set_billing_partner_id_name(self, partner_field_name):
        self.__class__._billing_partner_id_name = partner_field_name
