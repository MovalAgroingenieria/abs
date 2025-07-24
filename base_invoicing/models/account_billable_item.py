# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class AccountBillableItem(models.AbstractModel):
    _name = 'account.billable.item'
    _description = ('Abstract model inherited by any concrete model '
                    'that contains billable records')

    # Name of the field in the billable items model that serves as the
    # reference to the partner.
    _billing_partner_id_name = 'partner_id'

    # Name of the field in the billable items model that plays the role
    # of quantity.
    _billing_quantity_name = 'quantity'

    # Name of the field in the billable items model that plays the role
    # of "additional grouping criterion".
    _billing_groupvalue_name = ''

    billing_partner_id = fields.Many2one(
        string='Billing partner reference',
        comodel_name='res.partner',
        compute='_compute_billing_partner_id',)

    billing_quantity = fields.Float(
        string='Quantity field name',
        digits=(32, 4),
        compute='_compute_billing_quantity',)

    billing_groupvalue = fields.Char(
        string='Grouping Value',
        compute='_compute_billing_groupvalue',)

    number_of_invoices = fields.Integer(
        string='No. of invoices',
        default=0,
        readonly=1,)

    move_line_ids = fields.One2many(
        string='Invoice Lines',
        comodel_name='account.move.line',
        compute='_compute_move_line_ids',)

    def _compute_billing_partner_id(self):
        for record in self:
            billing_partner_id = None
            if self._billing_partner_id_name:
                billing_partner_id = getattr(record,
                                             self._billing_partner_id_name)
            record.billing_partner_id = billing_partner_id

    def _compute_billing_quantity(self):
        for record in self:
            billing_quantity = 1
            if self._billing_quantity_name:
                billing_quantity = getattr(record,
                                           self._billing_quantity_name)
            record.billing_quantity = billing_quantity

    def _compute_billing_groupvalue(self):
        for record in self:
            billing_groupvalue = ''
            if self._billing_groupvalue_name:
                billing_groupvalue = str(
                    getattr(record, self._billing_groupvalue_name))
            record.billing_groupvalue = billing_groupvalue

    def _compute_move_line_ids(self):
        for record in self:
            move_line_ids = None
            related_move_lines = self.env['account.move.line'].search(
                [('billable_item_model', '=', self._name),
                 ('billable_item_res_id', '=', record.id)])
            if related_move_lines:
                move_line_ids = related_move_lines.ids
            record.move_line_ids = move_line_ids

    @api.model
    def set_billing_quantity_name(self, quantity_name):
        self.__class__._billing_quantity_name = quantity_name

    @api.model
    def set_billing_groupvalue_name(self, groupvalue_name):
        self.__class__._billing_groupvalue_name = groupvalue_name

    @api.model
    def exists_active_field(self, model_name):
        resp = False
        active_field = self.env['common.metadata'].get_field(
            model_name, 'active')
        if active_field and active_field['ttype'] == 'boolean':
            resp = True
        return resp

    @api.model
    def inherits_from_account_billable_item(self, model_name):
        resp = False
        inherited_models = self.env['common.metadata'].get_inherited_models(
            model_name)
        if inherited_models:
            inherited_models_str = str(inherited_models)
            if 'account.billable.item' in inherited_models:
                resp = True
        return resp
