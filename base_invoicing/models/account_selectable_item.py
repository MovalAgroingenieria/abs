# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from jinja2 import Template, TemplateError
from odoo import models, fields, api, _


class AccountSelectableItem(models.Model):
    _name = 'account.selectable.item'
    _description = 'Selectable item for invoicing'

    productlink_id = fields.Many2one(
        string='Product of invoice set',
        comodel_name='account.invoiceset.productlink',
        ondelete='cascade',)

    billable_item_model = fields.Char(
        string='Billable item model: name',)

    billable_item_res_id = fields.Many2oneReference(
        string='Billable item model: reference',
        model_field='billable_item_model',)

    partner_id = fields.Many2one(
        string='Customer',
        comodel_name='res.partner',)

    quantity = fields.Float(
        string='Quantity',
        digits=(32, 4),)

    selected = fields.Boolean(
        string='Selected (y/n)',)

    rendered_aux_desc = fields.Text(
        string='Additional Information',
        compute='_compute_rendered_aux_desc',)

    aux_01_char = fields.Char(
        string='Aux. field of type char #1',)

    aux_01_int = fields.Integer(
        string='Aux. field of type integer #1',)

    aux_01_float = fields.Float(
        string='Aux. field of type float #1',
        digits=(32, 4),)

    aux_01_bool = fields.Boolean(
        string='Aux. field of type boolean #1',)

    aux_02_char = fields.Char(
        string='Aux. field of type char #2',)

    aux_02_int = fields.Integer(
        string='Aux. field of type integer #2',)

    aux_02_float = fields.Float(
        string='Aux. field of type float #2',
        digits=(32, 4),)

    aux_02_bool = fields.Boolean(
        string='Aux. field of type boolean #2',)

    aux_03_char = fields.Char(
        string='Aux. field of type char #3',)

    aux_03_int = fields.Integer(
        string='Aux. field of type integer #3',)

    aux_03_float = fields.Float(
        string='Aux. field of type float #3',
        digits=(32, 4),)

    aux_03_bool = fields.Boolean(
        string='Aux. field of type boolean #3',)

    def _compute_rendered_aux_desc(self):
        for record in self:
            rendered_aux_desc = ''
            if (record.productlink_id.categ_id.aux_desc and
               record.billable_item_model and record.billable_item_res_id):
                my_billable_item = \
                    self.env[record.billable_item_model].browse(
                        record.billable_item_res_id)
                if my_billable_item:
                    try:
                        template = Template(
                            record.productlink_id.categ_id.aux_desc)
                        rendered_aux_desc = template.render(
                            billable_item=my_billable_item,)
                    except TemplateError as e:
                        rendered_aux_desc = _('Error in template:') + ' ' + e.message()
                if record.productlink_id.categ_id.aux_desc.find('|') != -1:
                    rendered_aux_desc = rendered_aux_desc.replace('|', '\n')
            record.rendered_aux_desc = rendered_aux_desc

    def action_select_items(self):
        self.selected = True
