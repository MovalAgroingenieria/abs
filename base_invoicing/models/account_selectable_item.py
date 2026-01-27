# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from jinja2 import Template, TemplateError
from odoo import _, api, fields, models


class AccountSelectableItem(models.Model):
    _name = "account.selectable.item"
    _description = "Selectable item for invoicing"

    productlink_id = fields.Many2one(
        comodel_name="account.invoiceset.productlink",
        ondelete="cascade",
        string="Product of invoice set",
    )
    billable_item_model = fields.Char(string="Billable item model: name")
    billable_item_res_id = fields.Many2oneReference(
        model_field="billable_item_model",
        string="Billable item model: reference",
    )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Customer")
    quantity = fields.Float(digits=(32, 4), string="Quantity")

    state = fields.Selection(
        related="productlink_id.invoiceset_id.state",
        string="State",
    )
    selected = fields.Boolean(string="Selected (y/n)")
    selected_message = fields.Char(
        compute="_compute_selected_message",
        string="Selected (message)",
    )
    rendered_aux_desc = fields.Text(
        compute="_compute_rendered_aux_desc",
        string="Additional Information",
    )

    aux_01_char = fields.Char(string="Aux. field of type char #1")
    aux_01_int = fields.Integer(string="Aux. field of type integer #1")
    aux_01_float = fields.Float(digits=(32, 4), string="Aux. field of type float #1")
    aux_01_bool = fields.Boolean(string="Aux. field of type boolean #1")

    aux_02_char = fields.Char(string="Aux. field of type char #2")
    aux_02_int = fields.Integer(string="Aux. field of type integer #2")
    aux_02_float = fields.Float(digits=(32, 4), string="Aux. field of type float #2")
    aux_02_bool = fields.Boolean(string="Aux. field of type boolean #2")

    aux_03_char = fields.Char(string="Aux. field of type char #3")
    aux_03_int = fields.Integer(string="Aux. field of type integer #3")
    aux_03_float = fields.Float(digits=(32, 4), string="Aux. field of type float #3")
    aux_03_bool = fields.Boolean(string="Aux. field of type boolean #3")

    @api.depends("selected")
    def _compute_selected_message(self):
        for record in self:
            record.selected_message = (
                _("Selected") if record.selected else _("Excluded")
            )

    @api.depends(
        "billable_item_model",
        "billable_item_res_id",
        "productlink_id.categ_id.aux_desc",
    )
    def _compute_rendered_aux_desc(self):
        for record in self:
            template_src = record.productlink_id.categ_id.aux_desc
            if (
                not template_src
                or not record.billable_item_model
                or not record.billable_item_res_id
            ):
                record.rendered_aux_desc = ""
                continue

            billable_item = self.env[record.billable_item_model].browse(
                record.billable_item_res_id
            )
            if not billable_item.exists():
                record.rendered_aux_desc = ""
                continue

            try:
                rendered = Template(template_src).render(billable_item=billable_item)
            except TemplateError as err:
                rendered = _("Error in template: %s") % str(err)

            if "|" in template_src:
                rendered = rendered.replace("|", "\n")

            record.rendered_aux_desc = rendered

    def action_select_items(self):
        self.write({"selected": True})
        self._update_productlink_populated()

    def action_deselect_items(self):
        self.write({"selected": False})
        self._update_productlink_populated()

    def _update_productlink_populated(self):
        productlinks = self.mapped("productlink_id").exists()
        if not productlinks:
            return

        selectable_item_model = self.env["account.selectable.item"]
        for productlink in productlinks:
            count_selected = selectable_item_model.search_count(
                [("productlink_id", "=", productlink.id), ("selected", "=", True)]
            )
            productlink.write({"populated": bool(count_selected)})
