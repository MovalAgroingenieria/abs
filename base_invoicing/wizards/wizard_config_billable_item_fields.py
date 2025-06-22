# -*- coding: utf-8 -*-
# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class WizardConfigBillableItemFields(models.TransientModel):
    _name = 'wizard.config.billable.item.fields'
    _description = ('Dialog box to configure the fields of the'
                    'billable items model')

    info_billable_item_model_id = fields.Char(
        string='Billable-items Model',)

    info_billable_item_quantity_field = fields.Char(
        string='Quantity Field',)

    billable_item_group_field = fields.Char(
        string='Field for grouping',)

    billable_item_detail_desc = fields.Char(
        string='Template for invoice lines',
        translate=True,)

    billable_item_domain = fields.Char(
        string='Pre-filter on billable items',)

    category_code = fields.Integer(
        string='Category Code',)

    @api.model
    def default_get(self, var_fields):
        resp = None
        record = self.env['account.invoiceset.productlink'].browse(
            self.env.context['active_id'])
        if record:
            info_billable_item_model_id = \
                record.billable_item_model_id.sudo().model + ' (' + \
                record.billable_item_model_id.sudo().name + ')'
            info_billable_item_quantity_field = \
                record.billable_item_quantity_field
            if info_billable_item_quantity_field:
                info_billable_item_quantity_field = info_billable_quantity_field + \
                    ' (' + record.billable_item_quantity_label + ')'
            resp = {
                'info_billable_item_model_id':
                    info_billable_item_model_id,
                'info_billable_item_quantity_field':
                    info_billable_item_quantity_field,
                'billable_item_group_field':
                    record.billable_item_group_field,
                'billable_item_detail_desc':
                    record.billable_item_detail_desc,
                'billable_item_domain':
                    record.billable_item_domain,
                'category_code':
                    record.categ_id.category_code,
            }
        return resp

    def set_config_fields(self):
        self.ensure_one
        record = self.env['account.invoiceset.productlink'].browse(
            self.env.context['active_id'])
        if record:
            record.write({
                'billable_item_group_field': self.billable_item_group_field,
                'billable_item_detail_desc': self.billable_item_detail_desc,
                'billable_item_domain': self.billable_item_domain,
            })
