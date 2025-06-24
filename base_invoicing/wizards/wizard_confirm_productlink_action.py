# -*- coding: utf-8 -*-
# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class WizardConfirmProductlinkAction(models.TransientModel):
    _name = 'wizard.confirm.productlink.action'
    _description = 'Dialog box to confirm a product-link action'

    confirm_message = fields.Char(
        string='Confirmation Message',)

    operation = fields.Char(
        string='Operation Type',)

    @api.model
    def default_get(self, var_fields):
        confirm_message = self.env.context.get('confirm_message', '')
        operation = self.env.context.get('operation', '')
        return {
            'confirm_message': confirm_message,
            'operation': operation,
        }

    def execute_operation(self):
        self.ensure_one
        record = self.env['account.invoiceset.productlink'].browse(
            self.env.context['active_id'])
        if record and self.operation:
            if self.operation == 'refresh_selectable_items':
                record.refresh_selectable_items()
            elif self.operation == 'delete_selectable_items':
                record.delete_selectable_items()
            elif self.operation == 'delete':
                record.delete()
