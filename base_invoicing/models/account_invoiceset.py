# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, api, _


class AccountInvoiceset(models.Model):
    _name = 'account.invoiceset'
    _description = 'Invoice Set'
    _inherit = ['simple.model', 'mail.thread']

    # Static variables inherited from "simple.model"
    _set_num_code = False
    _sequence_for_codes = 'base_invoicing.mass_invoicing_seq_invoiceset_code_id'
    _size_name = 20
    _minlength = 0
    _maxlength = 20
    _allowed_blanks_in_code = False
    _set_alphanum_code_to_lowercase = False
    _set_alphanum_code_to_uppercase = True
    _size_description = 100

    # Modified fields
    alphanum_code = fields.Char(
        string='Code of invoice set',
        required=True,)

    description = fields.Char(
        string='Description of invoice set',
        required=True,
        translate=True,)

    invoice_date = fields.Date(
        string='Invoicing Date',
        default=lambda self: fields.datetime.now(),
        required=True,
        index=True,)

    invoice_date_due = fields.Date(
        string='Due Date',)

    journal_id = fields.Many2one(
        string='Journal',
        comodel_name='account.journal',)

    payment_term_id = fields.Many2one(
        string='Payment Term',
        comodel_name='account.payment.term',)

    invoice_user_id = fields.Many2one(
        string='Sales Person',
        comodel_name='res.users',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,)

    state = fields.Selection(
        string='State',
        selection=[
            ('draft', 'Draft'),
            ('configured', 'Configured'),
            ('calculating', 'In progress'),
            ('calculated', 'Calculated'),
            ('committed', 'Committed'),
        ],
        default='draft',
        store=True,
        compute='_compute_state',
        index=True,)

    move_ids = fields.One2many(
        string='Invoices',
        comodel_name='account.move',
        inverse_name='invoiceset_id',)

    number_of_invoices = fields.Integer(
        string='Number of invoices',
        store=True,
        compute='_compute_number_of_invoices',)

    move_line_ids = fields.One2many(
        string='Invoice Lines',
        comodel_name='account.move.line',
        inverse_name='invoiceset_id',)

    productlink_ids = fields.One2many(
        string='Invoice-Set Lines',
        comodel_name='account.invoiceset.productlink',
        inverse_name='invoiceset_id',)

    all_productlinks_configured = fields.Boolean(
        string='All product-links are configured (y/n)',
        default=False,
        store=True,
        compute='_compute_all_productlinks_configured',)

    calculating = fields.Boolean(
        string='In calculation process (y/n)',
        default=False,
        required=True,
        readonly=True,)

    invoice_generation_progress = fields.Float(
        string='Percentage of progress during invoice generation',
        default=0,
        readonly=True,)

    calculated = fields.Boolean(
        string='Calculated (y/n)',
        default=False,
        required=True,
        readonly=True,)

    some_posted_invoice = fields.Boolean(
        string='Some posted invoice (y/n)',
        default=False,
        store=True,
        compute='_compute_some_posted_invoice',)

    # Provisional
    @api.depends('calculating')
    def _compute_state(self):
        for record in self:
            state = 'draft'
            # Provisional
            record.state = state

    @api.depends('move_ids')
    def _compute_number_of_invoices(self):
        for record in self:
            number_of_invoices = 0
            if record.move_ids:
                number_of_invoices = len(record.move_ids)
            record.number_of_invoices = number_of_invoices

    # Provisional
    @api.depends('productlink_ids')
    def _compute_all_productlinks_configured(self):
        for record in self:
            all_productlinks_configured = False
            # Provisional
            record.all_productlinks_configured = all_productlinks_configured

    @api.depends('move_ids', 'move_ids.state')
    def _compute_some_posted_invoice(self):
        for record in self:
            some_posted_invoice = False
            if record.move_ids:
                some_posted_invoice = any(invoice.state == 'posted'
                                          for invoice in record.move_ids)
            record.some_posted_invoice = some_posted_invoice

    def action_show_invoices(self):
        self.ensure_one()
        current_invoiceset = self
        id_tree_view = self.sudo().env.ref(
            'base_invoicing.view_out_invoice_tree').id
        id_form_view = self.sudo().env.ref(
            'base_invoicing.view_move_form').id
        search_view = self.sudo().env.ref(
            'base_invoicing.view_account_invoice_filter')
        act_window = {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'views': [(id_tree_view, 'tree'), (id_form_view, 'form'),],
            'search_view_id': (search_view.id, search_view.name),
            'target': 'current',
            'domain': [('invoiceset_id', '=', current_invoiceset.id)],
            }
        return act_window

    def calculate_invoiceset(self):
        self.ensure_one()
        # Provisional
        print('calculate_invoiceset')

    def cancel_invoiceset(self):
        self.ensure_one()
        # Provisional
        print('cancel_invoiceset')

    def cancel_invoices(self):
        self.ensure_one()
        # Provisional
        print('cancel_invoices')


class AccountInvoicesetProductlink(models.Model):
    _name = 'account.invoiceset.productlink'
    _description = 'Product of invoice set'

    # Size of the "name" field in the model.
    MAX_SIZE_PRODUCTLINK_CODE = 100

    invoiceset_id = fields.Many2one(
        string='Invoice Set',
        comodel_name='account.invoiceset',
        index=True,
        ondelete='cascade',)

    product_id = fields.Many2one(
        string='Product',
        comodel_name='product.product',
        required=True,
        index=True,
        ondelete='restrict',)

    name = fields.Char(
        string='Identifier of productlink',
        size=MAX_SIZE_PRODUCTLINK_CODE,
        store=True,
        index=True,
        compute='_compute_name',)

    @api.depends('invoiceset_id', 'invoiceset_id.alphanum_code',
                 'product_id', 'product_id.product_tmpl_id.name')
    def _compute_name(self):
        for record in self:
            name = ''
            if record.invoiceset_id and record.product_id:
                name = record.invoiceset_id.alphanum_code + \
                    record.product_id.product_tmpl_id.name
            record.name = name[:self.MAX_SIZE_PRODUCTLINK_CODE]
