# -*- coding: utf-8 -*-
# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class WizardConfigBillableItemFields(models.TransientModel):
    _name = 'wizard.config.billable.item.fields'
    _description = ('Dialog box to configure the fields of the'
                    'billable items model')

    billable_item_model_id = fields.Many2one(
        string='Billable-items Model',
        comodel_name='ir.model',)

    billable_item_quantity_field = fields.Char(
        string='Quantity Field',)

    billable_item_quantity_label = fields.Char(
        string='Label of the quantity field',
        translate=True, )

    billable_item_group_field = fields.Char(
        string='Field for grouping',)

    billable_item_detail_desc = fields.Char(
        string='Template for invoice lines',
        translate=True,)

    billable_item_domain = fields.Char(
        string='Pre-filter on billable items',)

    @api.model
    def default_get(self, var_fields):
        resp = None
        record = self.env['account.invoiceset.productlink'].browse(
            self.env.context['active_id'])
        if record:
            resp = {
                'billable_item_model_id':
                    record.categ_id.billable_item_model_id,
                'billable_item_quantity_field':
                    record.categ_id.billable_item_quantity_field,
                'billable_item_quantity_label':
                    record.categ_id.billable_item_quantity_label,
                'billable_item_group_field':
                    record.categ_id.billable_item_group_field,
                'billable_item_detail_desc':
                    record.categ_id.billable_item_detail_desc,
                'billable_item_domain':
                    record.categ_id.billable_item_domain,
            }
        return resp

    def set_config_fields(self):
        self.ensure_one
        # Provisional
        print('set_config_fields')
