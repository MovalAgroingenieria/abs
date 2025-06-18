# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models


class CommonMetadata(models.AbstractModel):
    _name = 'common.metadata'
    _description = 'Metadata extraction from Odoo models'

    # Get the metadata of a field in a model.
    def get_field(self, model_name, field_name):
        resp = {'model': model_name, 'name': field_name, }
        model_ir_model_fields = self.env['ir.model.fields'].sudo()
        field = model_ir_model_fields.search(
            [('model', '=', model_name), ('name', '=', field_name)])
        if field:
            field = field[0]
        else:
            return False
        resp['field_description'] = field.field_description
        resp['ttype'] = field.ttype
        resp['relation'] = field.relation
        resp['on_delete'] = field.on_delete
        resp['relation_field'] = field.relation_field
        resp['required'] = field.required
        resp['readonly'] = field.readonly
        resp['store'] = field.store
        resp['index'] = field.index
        resp['copied'] = field.copied
        resp['domain'] = field.domain
        return resp

    # Get the models with any Many2one reference to another model
    # ("model_name"). The "many2one_name" parameter, if present, sets the name
    # of the Many2one reference.
    def get_models_with_many2one(self, model_name, many2one_name='',
                                 include_model=True):
        resp = []
        model_ir_model = self.env['ir.model'].sudo()
        reference_model = model_ir_model.search([('model', '=', model_name)])
        if reference_model:
            if include_model:
                resp.append(reference_model)
            all_models = model_ir_model.search(
                [('model', '!=', model_name), ('transient', '=', False)])
            for model in all_models:
                for field in model.field_id:
                    if (field.ttype == 'many2one' and
                       field.relation == model_name and
                       (many2one_name == '' or many2one_name == field.name)):
                        resp.append(model)
                        break
        return resp

    # Obtain the metadata of the fields in a model, with a filter based on the
    # field type (example: "integer,float").
    def get_fields(self, model_name, field_types, exclude_id=True,
                   exclude_computed=True):
        resp = []
        field_types = field_types.lower()
        condition = [('model', '=', model_name)]
        if exclude_id:
            condition.append(('name', '!=', 'id'))
        if exclude_computed:
            condition.append(('store', '=', True))
        additional_condition = self._get_condition(field_types)
        if additional_condition:
            condition = condition + additional_condition
        model_ir_model_fields = self.env['ir.model.fields'].sudo()
        fields = model_ir_model_fields.search(condition)
        for field in fields:
            resp.append({
                'name': field.name,
                'field_description': field.field_description
            })
        return resp

    def _get_condition(self, field_types):
        resp = []
        if field_types:
            pos_sep = field_types.find(',')
            if pos_sep == -1:
                resp.append(('ttype', '=', field_types))
            else:
                current_field_type = field_types[:pos_sep]
                remaining_field_types = field_types[pos_sep+1:]
                resp.append('|')
                resp.append(('ttype', '=', current_field_type))
                resp = resp + self._get_condition(remaining_field_types)
        return resp
