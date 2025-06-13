# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, api, _


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
        store=True,
        compute='_compute_supports_mass_billing',)

    _sql_constraints = [
        ('category_code_ok', 'CHECK (category_code >= 0)',
         'Incorrect value for "Category Code".'),
    ]

    def _compute_supports_mass_billing(self):
        for record in self:
            supports_mass_billing = False
            if record.billable_item_model_id:
                supports_mass_billing = True
            record.supports_mass_billing = supports_mass_billing

    @api.onchange('billable_item_quantity_field')
    def _onchange_billable_item_quantity_field(self):
        billable_item_model_id = self.billable_item_model_id
        billable_item_quantity_field = self.billable_item_quantity_field
        if billable_item_model_id and billable_item_quantity_field:
            field_metadata = self.env['common.metadata'].get_field(
                billable_item_model_id.model, billable_item_quantity_field)
            if field_metadata:
                self.billable_item_quantity_label = \
                    field_metadata['field_description']

    def name_get(self):
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
                            (category.id, category_name[1] + ' (' + _('cat. #') +
                             str(category.category_code) + ')'))
                else:
                    new_category_names.append(category_name)
            category_names = new_category_names
        return category_names

    def action_select_billable_item_field(self):
        self.ensure_one()
        # Provisional
        print('action_select_billable_item_quantity_field')
        print('field = ' + str(self.env.context.get('field', False)))
        print('types = ' + str(self.env.context.get('types', False)))
