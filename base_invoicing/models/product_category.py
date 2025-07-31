# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api, exceptions, _


class ProductCategory(models.Model):
    _inherit = ['product.category']

    def _get_billable_item_model_id_domain(self):
        valid_models = []
        models_with_many2one_to_res_partner = \
            self.env['common.metadata'].get_models_with_many2one(
                'res.partner', many2one_name='partner_id', include_model=True)
        for model in models_with_many2one_to_res_partner or []:
            valid_models.append(model.id)
        return [('id', 'in', valid_models)]

    name = fields.Char(
        translate=True,)

    category_code = fields.Integer(
        string='Category Code',
        default=0,
        required=True,
        readonly=True,
        index=True,)

    billable_item_model_id = fields.Many2one(
        string='Billable-items Model',
        comodel_name='ir.model',
        domain=_get_billable_item_model_id_domain,)

    billable_item_quantity_field = fields.Char(
        string='Quantity Field',)

    billable_item_quantity_label = fields.Char(
        string='Label of the quantity field',
        store=True,
        compute='_compute_billable_item_quantity_label',
        readonly=False,
        translate=True,)

    billable_item_group_field = fields.Char(
        string='Field for grouping',)

    billable_item_detail_desc = fields.Char(
        string='Template for invoice lines',
        translate=True,)

    billable_item_domain = fields.Char(
        string='Pre-filter on billable items',)

    supports_mass_billing = fields.Boolean(
        string='Supports massive billing (y/n)',
        default=False,
        store=True,
        compute='_compute_supports_mass_billing',)

    aux_01_char_field = fields.Char(
        string='Aux. field of type char #1',)

    aux_01_char_label = fields.Char(
        string='Label of the aux. field of type char #1',
        store=True,
        compute='_compute_aux_01_label',
        readonly=False,
        translate=True,)

    aux_01_int_field = fields.Char(
        string='Aux. field of type integer #1',)

    aux_01_int_label = fields.Char(
        string='Label of the aux. field of type integer #1',
        store=True,
        compute='_compute_aux_01_label',
        readonly=False,
        translate=True,)

    aux_01_float_field = fields.Char(
        string='Aux. field of type float #1',)

    aux_01_float_label = fields.Char(
        string='Label of the aux. field of type float #1',
        store=True,
        compute='_compute_aux_01_label',
        readonly=False,
        translate=True,)

    aux_01_bool_field = fields.Char(
        string='Aux. field of type boolean #1',)

    aux_01_bool_label = fields.Char(
        string='Label of the aux. field of type boolean #1',
        store=True,
        compute='_compute_aux_01_label',
        readonly=False,
        translate=True,)

    aux_02_char_field = fields.Char(
        string='Aux. field of type char #2',)

    aux_02_char_label = fields.Char(
        string='Label of the aux. field of type char #2',
        store=True,
        compute='_compute_aux_02_label',
        readonly=False,
        translate=True,)

    aux_02_int_field = fields.Char(
        string='Aux. field of type integer #2',)

    aux_02_int_label = fields.Char(
        string='Label of the aux. field of type integer #2',
        store=True,
        compute='_compute_aux_02_label',
        readonly=False,
        translate=True,)

    aux_02_float_field = fields.Char(
        string='Aux. field of type float #2',)

    aux_02_float_label = fields.Char(
        string='Label of the aux. field of type float #2',
        store=True,
        compute='_compute_aux_02_label',
        readonly=False,
        translate=True,)

    aux_02_bool_field = fields.Char(
        string='Aux. field of type boolean #2',)

    aux_02_bool_label = fields.Char(
        string='Label of the aux. field of type boolean #2',
        store=True,
        compute='_compute_aux_02_label',
        readonly=False,
        translate=True,)

    aux_03_char_field = fields.Char(
        string='Aux. field of type char #3',)

    aux_03_char_label = fields.Char(
        string='Label of the aux. field of type char #3',
        store=True,
        compute='_compute_aux_03_label',
        readonly=False,
        translate=True,)

    aux_03_int_field = fields.Char(
        string='Aux. field of type integer #3',)

    aux_03_int_label = fields.Char(
        string='Label of the aux. field of type integer #3',
        store=True,
        compute='_compute_aux_03_label',
        readonly=False,
        translate=True,)

    aux_03_float_field = fields.Char(
        string='Aux. field of type float #3',)

    aux_03_float_label = fields.Char(
        string='Label of the aux. field of type float #3',
        store=True,
        compute='_compute_aux_03_label',
        readonly=False,
        translate=True,)

    aux_03_bool_field = fields.Char(
        string='Aux. field of type boolean #3',)

    aux_03_bool_label = fields.Char(
        string='Label of the aux. field of type boolean #3',
        store=True,
        compute='_compute_aux_03_label',
        readonly=False,
        translate=True,)

    aux_desc = fields.Char(
        string='Wildcard Template',
        translate=True,)

    _sql_constraints = [
        ('category_code_ok', 'CHECK (category_code >= 0)',
         'Incorrect value for "Category Code".'),
    ]

    @api.depends('billable_item_model_id',
                 'billable_item_quantity_field')
    def _compute_billable_item_quantity_label(self):
        for record in self:
            billable_item_model_id = record.billable_item_model_id
            billable_item_quantity_field = record.billable_item_quantity_field
            if billable_item_model_id and billable_item_quantity_field:
                field_metadata = self.env['common.metadata'].get_field(
                    billable_item_model_id.model, billable_item_quantity_field)
                if field_metadata:
                    record.billable_item_quantity_label = \
                        field_metadata['field_description']

    @api.depends('billable_item_model_id')
    def _compute_supports_mass_billing(self):
        for record in self:
            supports_mass_billing = False
            if record.billable_item_model_id:
                supports_mass_billing = True
            record.supports_mass_billing = supports_mass_billing

    @api.depends('billable_item_model_id',
                 'aux_01_char_field', 'aux_01_int_field',
                 'aux_01_float_field', 'aux_01_bool_field')
    def _compute_aux_01_label(self):
        for record in self:
            billable_item_model_id = record.billable_item_model_id
            aux_01_char_field = record.aux_01_char_field
            aux_01_int_field = record.aux_01_int_field
            aux_01_float_field = record.aux_01_float_field
            aux_01_bool_field = record.aux_01_bool_field
            if billable_item_model_id:
                if aux_01_char_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_01_char_field)
                    if field_metadata:
                        record.aux_01_char_label = \
                            field_metadata['field_description']
                if aux_01_int_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_01_int_field)
                    if field_metadata:
                        record.aux_01_int_label = \
                            field_metadata['field_description']
                if aux_01_float_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_01_float_field)
                    if field_metadata:
                        record.aux_01_float_label = \
                            field_metadata['field_description']
                if aux_01_bool_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_01_bool_field)
                    if field_metadata:
                        record.aux_01_bool_label = \
                            field_metadata['field_description']

    @api.depends('billable_item_model_id',
                 'aux_02_char_field', 'aux_02_int_field',
                 'aux_02_float_field', 'aux_02_bool_field')
    def _compute_aux_02_label(self):
        for record in self:
            billable_item_model_id = record.billable_item_model_id
            aux_02_char_field = record.aux_02_char_field
            aux_02_int_field = record.aux_02_int_field
            aux_02_float_field = record.aux_02_float_field
            aux_02_bool_field = record.aux_02_bool_field
            if billable_item_model_id:
                if aux_02_char_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_02_char_field)
                    if field_metadata:
                        record.aux_02_char_label = \
                            field_metadata['field_description']
                if aux_02_int_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_02_int_field)
                    if field_metadata:
                        record.aux_02_int_label = \
                            field_metadata['field_description']
                if aux_02_float_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_02_float_field)
                    if field_metadata:
                        record.aux_02_float_label = \
                            field_metadata['field_description']
                if aux_02_bool_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_02_bool_field)
                    if field_metadata:
                        record.aux_02_bool_label = \
                            field_metadata['field_description']

    @api.depends('billable_item_model_id',
                 'aux_03_char_field', 'aux_03_int_field',
                 'aux_03_float_field', 'aux_03_bool_field')
    def _compute_aux_03_label(self):
        for record in self:
            billable_item_model_id = record.billable_item_model_id
            aux_03_char_field = record.aux_03_char_field
            aux_03_int_field = record.aux_03_int_field
            aux_03_float_field = record.aux_03_float_field
            aux_03_bool_field = record.aux_03_bool_field
            if billable_item_model_id:
                if aux_03_char_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_03_char_field)
                    if field_metadata:
                        record.aux_03_char_label = \
                            field_metadata['field_description']
                if aux_03_int_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_03_int_field)
                    if field_metadata:
                        record.aux_03_int_label = \
                            field_metadata['field_description']
                if aux_03_float_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_03_float_field)
                    if field_metadata:
                        record.aux_03_float_label = \
                            field_metadata['field_description']
                if aux_03_bool_field:
                    field_metadata = self.env['common.metadata'].get_field(
                        billable_item_model_id.model, aux_03_bool_field)
                    if field_metadata:
                        record.aux_03_bool_label = \
                            field_metadata['field_description']

    @api.constrains('category_code')
    def _check_category_code(self):
        for record in self:
            if record.category_code > 0:
                categories_mapped_to_category_code = \
                    self.env['product.category'].search(
                        [('category_code', '=', record.category_code)])
                if (categories_mapped_to_category_code and
                        len(categories_mapped_to_category_code) > 1):
                    raise exceptions.ValidationError(
                        _('Repeated category code.'))

    def name_get(self):
        if self.env.context.get('short_name_categories', False):
            category_names = []
            for record in self:
                category_name = record.name
                if record.category_code:
                    category_name = (category_name + ' (' + _('cat. #') +
                                     str(record.category_code) + ')')

                category_names.append((record.id, category_name))
            return category_names
        category_names = super(ProductCategory, self).name_get()
        if category_names:
            new_category_names = []
            for category_name in category_names:
                category = self.browse(category_name[0])
                if category.category_code > 0:
                    if category.category_code == 1:
                        new_category_names.append(
                            (category.id, category_name[1] +
                             ' (' + _('standard cat.') + ')'))
                    else:
                        new_category_names.append(
                            (category.id, category_name[1] + ' (' +
                             _('cat. #') + str(category.category_code) + ')'))
                else:
                    new_category_names.append(category_name)
            category_names = new_category_names
        return category_names

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals = self._update_vals(vals)
        categories = super(ProductCategory, self).create(vals_list)
        return categories

    def write(self, vals):
        vals = self._update_vals(vals)
        resp = super(ProductCategory, self).write(vals)
        return resp

    def _update_vals(self, vals):
        if ('billable_item_model_id' in vals and
           (not vals['billable_item_model_id'])):
            vals['billable_item_quantity_field'] = None
            vals['billable_item_quantity_label'] = None
            vals['billable_item_group_field'] = None
            vals['billable_item_detail_desc'] = None
            vals['billable_item_domain'] = None
            vals['aux_01_char_field'] = None
            vals['aux_01_char_label'] = None
            vals['aux_01_int_field'] = None
            vals['aux_01_int_label'] = None
            vals['aux_01_float_field'] = None
            vals['aux_01_float_label'] = None
            vals['aux_01_bool_field'] = None
            vals['aux_01_bool_label'] = None
            vals['aux_02_char_field'] = None
            vals['aux_02_char_label'] = None
            vals['aux_02_int_field'] = None
            vals['aux_02_int_label'] = None
            vals['aux_02_float_field'] = None
            vals['aux_02_float_label'] = None
            vals['aux_02_bool_field'] = None
            vals['aux_02_bool_label'] = None
            vals['aux_03_char_field'] = None
            vals['aux_03_char_label'] = None
            vals['aux_03_int_field'] = None
            vals['aux_03_int_label'] = None
            vals['aux_03_float_field'] = None
            vals['aux_03_float_label'] = None
            vals['aux_03_bool_field'] = None
            vals['aux_03_bool_label'] = None
        return vals

    def copy(self, default=None):
        default = dict(default or {})
        default['category_code'] = 0
        resp = super(ProductCategory, self).copy(default)
        return resp

    def action_select_billable_item_field(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Warning'),
                'message': _('It is mandatory to set the billable items '
                             'model.'),
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close', },
            }
        }
        if self.billable_item_model_id:
            name_value = _('Model') + ' : ' + self.billable_item_model_id.model + \
                ' (' + self.billable_item_model_id.name + ')',
            action = {
                'type': 'ir.actions.act_window',
                'name': name_value,
                'res_model': 'wizard.select.field',
                'view_mode': 'form',
                'target': 'new',
            }
        return action

    @api.model
    def _check_field(self, model_name, field_name, admissible_types):
        resp = False
        field_metadata = self.env['common.metadata'].get_field(
            model_name, field_name)
        if field_metadata:
            field_ttype = field_metadata['ttype']
            admissible_types = admissible_types.lower().split(',')
            if field_ttype in admissible_types:
                resp = True
        return resp
