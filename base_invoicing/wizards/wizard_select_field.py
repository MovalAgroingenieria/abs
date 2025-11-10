# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class FieldOption(models.TransientModel):
    _name = 'field.option'
    _description = 'Options for the wizard selection field (auxiliary model)'

    name = fields.Char()
    field_description = fields.Char()

    def name_get(self):
        return [(record.id, record.field_description) for record in self]


class WizardSelectField(models.TransientModel):
    _name = 'wizard.select.field'
    _description = 'Dialog box to select a field of the billable items model'

    selected_field_id = fields.Many2one(
        string='Selected Field',
        comodel_name='field.option',)

    @api.model
    def default_get(self, var_fields):
        if 'selected_field_id' in var_fields:
            record = self.env['product.category'].browse(
                self.env.context['active_id'])
            source_model = record.billable_item_model_id.model
            field_types = self.env.context.get('types', '')
            fields_metadata = self.env['common.metadata'].get_fields(
                source_model, field_types)
            model_field_option = self.env['field.option']
            model_field_option.search([]).unlink()
            for field_metadata in fields_metadata or []:
                model_field_option.create({
                    'name':
                        field_metadata['name'],
                    'field_description':
                        field_metadata['name'] + ' (' +
                        field_metadata['field_description'] + ')'
                })
        return {}

    def set_selected_field(self):
        self.ensure_one()
        record = self.env['product.category'].browse(
            self.env.context['active_id'])
        destination_field = self.env.context.get('field', False)
        if record and destination_field:
            record.write({
                destination_field: self.selected_field_id.name,
            })
