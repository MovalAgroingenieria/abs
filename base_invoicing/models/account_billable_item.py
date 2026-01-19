# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class AccountBillableItem(models.AbstractModel):
    _name = "account.billable.item"
    _description = "Abstract model for billable records"

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
        string="Quantity field name",
    )
    billing_groupvalue = fields.Char(
        compute="_compute_billing_groupvalue",
        string="Grouping Value",
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
        string="Product",
    )
    move_line_ids = fields.One2many(
        comodel_name="account.move.line",
        compute="_compute_move_line_ids",
        string="Invoice Lines",
    )

    @api.depends()
    def _compute_billing_partner_id(self):
        for record in self:
            field_name = record._billing_partner_id_name
            record.billing_partner_id = getattr(record, field_name, False) if field_name else False

    @api.depends()
    def _compute_billing_quantity(self):
        for record in self:
            field_name = record._billing_quantity_name
            record.billing_quantity = getattr(record, field_name, 1) if field_name else 1

    @api.depends()
    def _compute_billing_groupvalue(self):
        for record in self:
            field_name = record._billing_groupvalue_name
            value = getattr(record, field_name, False) if field_name else False
            record.billing_groupvalue = str(value) if value not in (False, None) else ""

    @api.depends()
    def _compute_move_line_ids(self):
        move_line_model = self.env["account.move.line"]
        for record in self:
            record.move_line_ids = move_line_model.search(
                [
                    ("billable_item_model", "=", record._name),
                    ("billable_item_res_id", "=", record.id),
                ]
            )

    @api.model
    def set_billing_quantity_name(self, quantity_name):
        self.__class__._billing_quantity_name = quantity_name

    @api.model
    def set_billing_groupvalue_name(self, groupvalue_name):
        self.__class__._billing_groupvalue_name = groupvalue_name

    @api.model
    def exists_active_field(self, model_name):
        field_meta = self.env["common.metadata"].get_field(
            model_name, "active", exclude_related=True
        )
        return bool(field_meta and field_meta.get("ttype") == "boolean")

    @api.model
    def inherits_from_account_billable_item(self, model_name):
        inherited_models = self.env["common.metadata"].get_inherited_models(model_name) or []
        return "account.billable.item" in inherited_models
