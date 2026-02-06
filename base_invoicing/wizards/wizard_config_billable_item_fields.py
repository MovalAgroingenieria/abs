# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class WizardConfigBillableItemFields(models.TransientModel):
    _name = "wizard.config.billable.item.fields"
    _description = "Configure billable item fields"

    info_billable_item_model_id = fields.Char(
        string="Billable-items Model",
        readonly=True,
    )
    info_billable_item_model_name = fields.Char(
        string="Billable model technical name",
        readonly=True,
    )
    info_billable_item_quantity_field = fields.Char(
        string="Quantity Field",
        readonly=True,
    )

    billable_item_group_field = fields.Char(string="Field for grouping")
    billable_item_detail_desc = fields.Char(
        string="Template for invoice lines",
        translate=True,
    )
    billable_item_domain = fields.Char(string="Pre-filter on billable items")

    category_code = fields.Integer(readonly=True)
    editable = fields.Boolean(
        string="Editable Wizard (y/n)",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_id = self.env.context.get("active_id")
        if not active_id:
            return res

        productlink = self.env["account.invoiceset.productlink"].browse(active_id)
        if not productlink.exists():
            return res

        model = productlink.billable_item_model_id
        quantity_field = productlink.billable_item_quantity_field

        res.update(
            {
                "info_billable_item_model_id": (
                    f"{model.model} ({model.name})" if model else False
                ),
                "info_billable_item_model_name": model.model if model else False,
                "info_billable_item_quantity_field": (
                    f"{quantity_field} ({productlink.billable_item_quantity_label})"
                    if quantity_field
                    else False
                ),
                "billable_item_group_field": productlink.billable_item_group_field,
                "billable_item_detail_desc": productlink.billable_item_detail_desc,
                "billable_item_domain": productlink.billable_item_domain,
                "category_code": productlink.categ_id.category_code,
                "editable": productlink.invoiceset_id.state in ("draft", "configured"),
            }
        )
        return res

    def set_config_fields(self):
        self.ensure_one()

        active_id = self.env.context.get("active_id")
        if not active_id:
            return {"type": "ir.actions.act_window_close"}

        productlink = self.env["account.invoiceset.productlink"].browse(active_id)
        if not productlink.exists():
            return {"type": "ir.actions.act_window_close"}

        productlink.write(
            {
                "billable_item_group_field": self.billable_item_group_field,
                "billable_item_detail_desc": self.billable_item_detail_desc,
                "billable_item_domain": self.billable_item_domain,
            }
        )
        return {"type": "ir.actions.act_window_close"}
