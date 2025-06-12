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
            models = model_ir_model.search(
                [('model', '!=', model_name), ('transient', '=', False)])
            for model in models:
                for field in model.field_id:
                    if (field.ttype == 'many2one' and
                       field.relation == model_name and
                       (many2one_name == '' or many2one_name == field.name)):
                        resp.append(model)
                        break
        return resp
