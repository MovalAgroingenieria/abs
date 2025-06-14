# -*- coding: utf-8 -*-
# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class WizardSelectField(models.TransientModel):
    _name = 'wizard.select.field'
    _description = 'Dialog box to select a field of the billable items model'

    def _get_fields_metadata(self):
        resp = []
        record = self.env['product.category'].browse(
            self.env.context['active_id'])
        source_model = record.billable_item_model_id.model
        field_types = self.env.context.get('types', '')
        fields_metadata = self.env['common.metadata'].get_fields(
            source_model, field_types)
        for field_metadata in fields_metadata or []:
            resp.append((field_metadata['name'],
                         field_metadata['name'] + ' (' +
                         field_metadata['field_description'] + ')'))
        return resp

    selected_field = fields.Selection(
        string='Selected Field',
        selection=_get_fields_metadata,
        required=True,)

    def set_selected_field(self):
        self.ensure_one()
        record = self.env['product.category'].browse(
            self.env.context['active_id'])
        destination_field = self.env.context.get('field', False)
        if record and destination_field:
            record.write({
                destination_field: self.selected_field,
            })
