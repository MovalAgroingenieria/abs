# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import time
import threading

from odoo import models, fields, api, exceptions, _


class AccountInvoiceset(models.Model):
    _name = 'account.invoiceset'
    _description = 'Invoice Set'
    _inherit = ['simple.model', 'mail.thread']
    _order = 'alphanum_code desc'

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

    # Indication of whether the stop button has been pressed (background).
    _stop_order = False

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
        required=True,)

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

    invoice_generation_progress = fields.Float(
        string='Percentage of progress during invoice generation',
        default=0,
        compute='_compute_invoice_generation_progress',)

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

    @api.depends('all_productlinks_configured')
    def _compute_state(self):
        for record in self:
            state = record.state
            transition_all_productlinks_configured = \
                record.all_productlinks_configured
            transition_some_unconfigured_productlink = \
                not transition_all_productlinks_configured
            if (state == 'draft' and
               transition_all_productlinks_configured):
                state = 'configured'
            if (state == 'configured' and
               transition_some_unconfigured_productlink):
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

    @api.depends('productlink_ids', 'productlink_ids.populated')
    def _compute_all_productlinks_configured(self):
        for record in self:
            all_productlinks_configured = False
            if record.productlink_ids:
                all_productlinks_configured = \
                    all(productlink.populated for
                        productlink in record.productlink_ids)
            record.all_productlinks_configured = all_productlinks_configured

    def _compute_invoice_generation_progress(self):
        model_account_invoiceset_progress = \
            self.env['account.invoiceset.progress']
        for record in self:
            invoice_generation_progress = 0
            progress_record = model_account_invoiceset_progress.search(
                [('invoiceset_id', '=', record.id)])
            if progress_record:
                invoice_generation_progress = \
                    progress_record[0].invoice_generation_progress
            record.invoice_generation_progress = invoice_generation_progress

    @api.depends('move_ids', 'move_ids.state')
    def _compute_some_posted_invoice(self):
        for record in self:
            some_posted_invoice = False
            if record.move_ids:
                some_posted_invoice = any(invoice.state == 'posted'
                                          for invoice in record.move_ids)
            record.some_posted_invoice = some_posted_invoice

    def name_get(self):
        invoiceset_names = []
        for record in self:
            invoiceset_name = record.alphanum_code
            if record.description:
                invoiceset_name = (invoiceset_name + ' (' +
                                   record.description + ')')
            invoiceset_names.append((record.id, invoiceset_name))
        return invoiceset_names

    @api.model_create_multi
    def create(self, vals_list):
        model_account_invoiceset_progress = \
            self.env['account.invoiceset.progress']
        invoicesets = super(AccountInvoiceset, self).create(vals_list)
        for invoiceset in invoicesets:
            model_account_invoiceset_progress.create({
                'invoiceset_id': invoiceset.id, })
        return invoicesets

    def unlink(self):
        model_account_invoiceset_progress = \
            self.env['account.invoiceset.progress']
        for record in self:
            model_account_invoiceset_progress.search(
                [('invoiceset_id', '=', record.id)]).unlink()
        res = super(AccountInvoiceset, self).unlink()
        return res

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
        invoiceset = self
        if not invoiceset.state == 'configured':
            return None
        # Set state to "calculating" with SQL
        # (ORM does not update until the end)
        self.env.cr.execute("""UPDATE account_invoiceset
        SET state = 'calculating' WHERE id = %s""", (invoiceset.id,))
        self.env.cr.execute("""DELETE FROM account_selectable_item
        WHERE NOT selected AND productlink_id IN
        (SELECT id FROM account_invoiceset_productlink
        WHERE invoiceset_id = %s)""", (invoiceset.id,))
        self.env.cr.commit()
        config = self.env['ir.config_parameter'].sudo()
        run_background = config.get_param(
            'base_invoicing.mass_invoicing_run_background', False)
        if run_background:
            self.calculation_process(invoiceset.id, True)
        else:
            self.calculation_process(invoiceset.id)

    # It is usually run from "cron".
    @api.model
    def calculate_all_configured_invoiceset(self):
        configured_invoicesets = self.search([('state', '=', 'configured')])
        for invoiceset in (configured_invoicesets or []):
            self.calculation_process(invoiceset.id, from_cron=True)

    @api.model
    def calculation_process(self, id_of_invoiceset,
                            background=False, from_cron=False):
        invoiceset = self.env['account.invoiceset'].browse(id_of_invoiceset)
        if not invoiceset:
            return None
        if background:
            new_cr = self.pool.cursor()
            env = api.Environment(new_cr, self.env.uid, self.env.context)
            self = self.with_env(env)
            background_process = threading.Thread(
                target=self.invoice_generation,
                args=(invoiceset.id, True, False), daemon=True)
            background_process.start()
        else:
            self.invoice_generation(id_of_invoiceset,
                                    from_cron=from_cron)

    @api.model
    def invoice_generation(self, id_of_invoiceset,
                           background=False, from_cron=False):
        number_of_invoices = 0
        invoiceset = self.env['account.invoiceset'].browse(id_of_invoiceset)
        if not invoiceset:
            return None
        # Provisional: replace "productlinks" with invoice list.
        productlinks = invoiceset.productlink_ids
        if not productlinks:
            return None
        suffix = _('(foreground)')
        if background:
            suffix = _('(background)')
        log_message = _('Calculation Process: start') + ' ' + suffix
        invoiceset.message_post(body=log_message)
        self.env['common.log'].register_in_log('Calculation Process: start.',
                                               source=self._name,
                                               message_type='INFO')
        invoice_generation_progress = 0
        step = 100/len(productlinks)
        tmp_cr = None
        if background:
            self.__class__._stop_order = False
            tmp_cr = self.pool.cursor()
            tmp_cr.execute("""UPDATE account_invoiceset_progress
                           SET invoice_generation_progress = %s
                           WHERE invoiceset_id = %s""",
                           (0, id_of_invoiceset))
            tmp_cr.commit()
        elif not from_cron:
            productlinks = productlinks.with_progress(
                _('Creating invoices...'))
        cancelled = False
        for productlink in (productlinks or []):
            # Provisional: create invoice.
            time.sleep(2)
            print(productlink.name)
            # Provisional: assign an invoice to a set of invoices.
            test_invoice = self.env['account.move'].browse(1)
            if test_invoice:
                test_invoice.invoiceset_id = id_of_invoiceset
            invoice_generation_progress = invoice_generation_progress + step
            if background:
                if self._stop_order:
                    invoiceset.cancel_invoices()
                    number_of_invoices = 0
                    self.__class__._stop_order = False
                    cancelled = True
                    break
                elif tmp_cr:
                    tmp_cr.execute("""UPDATE account_invoiceset_progress
                                   SET invoice_generation_progress = %s
                                   WHERE invoiceset_id = %s""",
                                   (invoice_generation_progress,
                                    id_of_invoiceset))
                    tmp_cr.commit()
        if not cancelled:
            state = 'calculated'
        else:
            state = 'configured'
        invoiceset.write({'state': state, })
        suffix = _('No. of invoices:') + ' ' + str(number_of_invoices)
        if cancelled:
            suffix = _('Cancelled')
        log_message = _('Calculation Process: end.') + ' ' + suffix
        invoiceset.message_post(body=log_message)
        self.env['common.log'].register_in_log(
            'Calculation Process: end. No. of invoices:' +
            ' ' + str(number_of_invoices),
            source=self._name, message_type='INFO')
        if background:
            self.env.cr.commit()
            self.env.cr.close()
            if tmp_cr:
                tmp_cr.execute("""UPDATE account_invoiceset_progress
                               SET invoice_generation_progress = %s
                               WHERE invoiceset_id = %s""",
                               (0, id_of_invoiceset))
                tmp_cr.commit()
                tmp_cr.close()
        return None

    def stop_calculation(self):
        self.ensure_one
        self.__class__._stop_order = True

    @api.model
    def background_calculation_active(self, invoiceset_id):
        resp = False
        invoiceset = self.sudo().browse(invoiceset_id)
        if invoiceset and invoiceset.state == 'calculating':
            config = self.env['ir.config_parameter'].sudo()
            run_background = config.get_param(
                'base_invoicing.mass_invoicing_run_background', False)
            if run_background:
                resp = True
        return resp

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

    def _get_product_id_domain(self):
        valid_products = []
        templ_with_mass_billing = self.env['product.template'].search(
            [('categ_id.supports_mass_billing', '=', True)])
        for tmpl in templ_with_mass_billing or []:
            for product in tmpl.product_variant_ids:
                valid_products.append(product.id)
        return [('id', 'in', valid_products)]

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
        domain=_get_product_id_domain,
        required=True,
        index=True,
        ondelete='restrict',)

    name = fields.Char(
        string='Identifier of productlink',
        size=MAX_SIZE_PRODUCTLINK_CODE,
        store=True,
        index=True,
        compute='_compute_name',)

    categ_id = fields.Many2one(
        string='Category',
        comodel_name='product.category',
        store=True,
        compute='_compute_categ_id',)

    lst_price = fields.Float(
        string='Price',
        store=True,
        compute='_compute_lst_price',)

    populated = fields.Boolean(
        string='Populated (y/n)',
        default=False,
        readonly=True,)

    billable_item_model_id = fields.Many2one(
        string='Billable-items Model',
        comodel_name='ir.model',
        store=True,
        compute='_compute_billable_item_model_id',)

    billable_item_quantity_field = fields.Char(
        string='Quantity Field',
        store=True,
        compute='_compute_billable_item_quantity_field',)

    billable_item_quantity_label = fields.Char(
        string='Label of the quantity field',
        related='product_id.product_tmpl_id.categ_id.'
                'billable_item_quantity_label',)

    billable_item_group_field = fields.Char(
        string='Field for grouping',
        store=True,
        compute='_compute_billable_item_group_field',
        readonly=False,)

    billable_item_detail_desc = fields.Char(
        string='Template for invoice lines',
        related='product_id.product_tmpl_id.categ_id.'
                'billable_item_detail_desc',)

    billable_item_domain = fields.Char(
        string='Pre-filter on billable items',
        store=True,
        compute='_compute_billable_item_domain',
        readonly=False,)

    selectable_item_ids = fields.One2many(
        string='Selectable Records',
        comodel_name='account.selectable.item',
        inverse_name='productlink_id',)

    number_of_selectable_items = fields.Integer(
        string='Number of selectable records',
        compute='_compute_number_of_selectable_items',)

    selected_item_ids = fields.One2many(
        string='Selected Records',
        comodel_name='account.selectable.item',
        compute='_compute_selected_item_ids',)

    number_of_selected_items = fields.Integer(
        string='Number of selected records',
        compute='_compute_number_of_selected_items',)

    _sql_constraints = [
        ('name_unique',
         'UNIQUE (name)',
         'Existing Product.'),
        ]

    @api.depends('invoiceset_id', 'invoiceset_id.alphanum_code',
                 'product_id', 'product_id.product_tmpl_id.name')
    def _compute_name(self):
        default_lang = self.env['ir.default'].get('res.partner', 'lang')
        if not default_lang:
            default_lang = 'en_US'
        for record in self:
            name = ''
            if record.invoiceset_id and record.product_id:
                name = record.invoiceset_id.alphanum_code + '-' + \
                    record.product_id.product_tmpl_id.with_context(
                        lang=default_lang).name
            record.name = name[:self.MAX_SIZE_PRODUCTLINK_CODE]

    @api.depends('product_id')
    def _compute_categ_id(self):
        for record in self:
            categ_id = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                categ_id = record.product_id.product_tmpl_id.categ_id
            record.categ_id = categ_id

    @api.depends('product_id')
    def _compute_lst_price(self):
        for record in self:
            lst_price = 0
            if record.product_id:
                lst_price = record.product_id.lst_price
            record.lst_price = lst_price

    @api.depends('product_id')
    def _compute_billable_item_model_id(self):
        for record in self:
            billable_item_model_id = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                billable_item_model_id = \
                    (record.product_id.product_tmpl_id.categ_id.
                     billable_item_model_id)
            record.billable_item_model_id = billable_item_model_id

    @api.depends('product_id')
    def _compute_billable_item_quantity_field(self):
        for record in self:
            billable_item_quantity_field = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                billable_item_quantity_field = \
                    (record.product_id.product_tmpl_id.categ_id.
                     billable_item_quantity_field)
            record.billable_item_quantity_field = billable_item_quantity_field

    @api.depends('product_id')
    def _compute_billable_item_quantity_label(self):
        for record in self:
            billable_item_quantity_label = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                billable_item_quantity_label = \
                    (record.product_id.product_tmpl_id.categ_id.
                     billable_item_quantity_label)
            record.billable_item_quantity_label = billable_item_quantity_label

    @api.depends('product_id')
    def _compute_billable_item_group_field(self):
        for record in self:
            billable_item_group_field = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                billable_item_group_field = \
                    (record.product_id.product_tmpl_id.categ_id.
                     billable_item_group_field)
            record.billable_item_group_field = billable_item_group_field

    @api.depends('product_id')
    def _compute_billable_item_domain(self):
        for record in self:
            billable_item_domain = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                billable_item_domain = \
                    (record.product_id.product_tmpl_id.categ_id.
                     billable_item_domain)
            record.billable_item_domain = billable_item_domain

    def _compute_number_of_selectable_items(self):
        for record in self:
            number_of_selectable_items = 0
            if record.selectable_item_ids:
                number_of_selectable_items = len(record.selectable_item_ids)
            record.number_of_selectable_items = number_of_selectable_items

    def _compute_selected_item_ids(self):
        for record in self:
            record.selected_item_ids = \
                record.selectable_item_ids.filtered(
                    lambda item: item.selected)

    def _compute_number_of_selected_items(self):
        for record in self:
            number_of_selected_items = 0
            if record.selected_item_ids:
                number_of_selected_items = len(record.selected_item_ids)
            record.number_of_selected_items = number_of_selected_items

    def action_config_billable_item_fields(self):
        self.ensure_one()
        act_window = {
            'type': 'ir.actions.act_window',
            'name': _('Product') + ' : ' +
                    self.product_id.product_tmpl_id.name,
            'res_model': 'wizard.config.billable.item.fields',
            'view_mode': 'form',
            'target': 'new',
        }
        return act_window

    def action_show_selectable_items(self):
        self.ensure_one()
        current_productlink = self
        if (current_productlink.invoiceset_id.state == 'draft' and
           current_productlink.number_of_selectable_items == 0):
            self.populate_selectable_items(current_productlink)
            self.update_populated()
        id_tree_view = self.sudo().env.ref(
            'base_invoicing.account_selectable_item_view_tree').id
        search_view = self.sudo().env.ref(
            'base_invoicing.account_selectable_item_view_search')
        title_prefix = _('Selectable Items. Product:')
        domain_conditions = [('productlink_id', '=', current_productlink.id)]
        if (current_productlink.invoiceset_id.state
           not in ['draft', 'configured']):
            title_prefix = _('Selected Items. Product:')
            domain_conditions.append(('selected', '=', True))
        act_window = {
            'type': 'ir.actions.act_window',
            'name': title_prefix + ' ' +
                    current_productlink.product_id.product_tmpl_id.name,
            'res_model': 'account.selectable.item',
            'view_mode': 'tree',
            'views': [(id_tree_view, 'tree'),],
            'search_view_id': (search_view.id, search_view.name),
            'target': 'current',
            'domain': domain_conditions,
            'context': self._get_context_hide_fields(
                current_productlink.categ_id,
                current_productlink.invoiceset_id.state),
            }
        return act_window

    @api.model
    def _get_context_hide_fields(self, category, current_state='draft'):
        context = {}
        if not category.billable_item_quantity_field:
            context['hide_quantity'] = True
        else:
            context['billable_item_quantity_label'] = \
                category.billable_item_quantity_label
        if not category.aux_01_char_field:
            context['hide_aux_01_char'] = True
        else:
            context['aux_01_char_label'] = category.aux_01_char_label
        if not category.aux_01_int_field:
            context['hide_aux_01_int'] = True
        else:
            context['aux_01_int_label'] = category.aux_01_int_label
        if not category.aux_01_float_field:
            context['hide_aux_01_float'] = True
        else:
            context['aux_01_float_label'] = category.aux_01_float_label
        if not category.aux_01_bool_field:
            context['hide_aux_01_bool'] = True
        else:
            context['aux_01_bool_label'] = category.aux_01_bool_label
        if not category.aux_02_char_field:
            context['hide_aux_02_char'] = True
        else:
            context['aux_02_char_label'] = category.aux_02_char_label
        if not category.aux_02_int_field:
            context['hide_aux_02_int'] = True
        else:
            context['aux_02_int_label'] = category.aux_02_int_label
        if not category.aux_02_float_field:
            context['hide_aux_02_float'] = True
        else:
            context['aux_02_float_label'] = category.aux_02_float_label
        if not category.aux_02_bool_field:
            context['hide_aux_02_bool'] = True
        else:
            context['aux_02_bool_label'] = category.aux_02_bool_label
        if not category.aux_03_char_field:
            context['hide_aux_03_char'] = True
        else:
            context['aux_03_char_label'] = category.aux_03_char_label
        if not category.aux_03_int_field:
            context['hide_aux_03_int'] = True
        else:
            context['aux_03_int_label'] = category.aux_03_int_label
        if not category.aux_03_float_field:
            context['hide_aux_03_float'] = True
        else:
            context['aux_03_float_label'] = category.aux_03_float_label
        if not category.aux_03_bool_field:
            context['hide_aux_03_bool'] = True
        else:
            context['aux_03_bool_label'] = category.aux_03_bool_label
        if not category.aux_desc:
            context['hide_rendered_aux_desc'] = True
        if current_state != 'draft' and current_state != 'configured':
            context['hide_selectors'] = True
        return context

    def action_refresh_selectable_items(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Warning'),
                'message': _('This operation is only allowed when the '
                             'invoice set is in the \'draft\' or'
                             ' \'configured\' state.'),
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close', },
            }
        }
        if (self.invoiceset_id.state == 'draft' or
           self.invoiceset_id.state == 'configured'):
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Product') + ' : ' +
                        self.product_id.product_tmpl_id.name,
                'res_model': 'wizard.confirm.productlink.action',
                'view_mode': 'form',
                'target': 'new',
                'context': {'confirm_message': _('You are about to refresh the'
                                                 ' lines associated with this '
                                                 'product. This will cause the'
                                                 ' current selection to be '
                                                 'lost.'),
                            'operation': 'refresh_selectable_items'}
            }
        return action

    def action_delete_selectable_items(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Warning'),
                'message': _('This operation is only allowed when the '
                             'invoice set is in the \'draft\' or'
                             ' \'configured\' state.'),
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close', },
            }
        }
        if (self.invoiceset_id.state == 'draft' or
           self.invoiceset_id.state == 'configured'):
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Product') + ' : ' +
                        self.product_id.product_tmpl_id.name,
                'res_model': 'wizard.confirm.productlink.action',
                'view_mode': 'form',
                'target': 'new',
                'context': {'confirm_message': _('You are about to delete all '
                                                 'lines associated with this '
                                                 'product.'),
                            'operation': 'delete_selectable_items'}
            }
        return action

    def action_delete_line(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Warning'),
                'message': _('This operation is only allowed when the '
                             'invoice set is in the \'draft\' or'
                             ' \'configured\' state.'),
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close', },
            }
        }
        if (self.invoiceset_id.state == 'draft' or
           self.invoiceset_id.state == 'configured'):
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Product') + ' : ' +
                        self.product_id.product_tmpl_id.name,
                'res_model': 'wizard.confirm.productlink.action',
                'view_mode': 'form',
                'target': 'new',
                'context': {'confirm_message': _('You are about to remove this '
                                                 'product from the invoice set.'
                                                 ' Therefore, its associated '
                                                 'lines will also be deleted.'),
                            'operation': 'delete'}
            }
        return action

    def refresh_selectable_items(self):
        self.delete_selectable_items()
        for record in self:
            self.populate_selectable_items(record)
        self.update_populated()

    def delete_selectable_items(self):
        for record in self:
            try:
                self.env.cr.savepoint()
                self.env.cr.execute("""DELETE FROM account_selectable_item
                WHERE productlink_id = %s""", (record.id,))
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                raise exceptions.UserError(_('Error updating records:') +
                                           ' ' + str(e))
            record.update_populated()

    def delete(self):
        for record in self:
            record.unlink()

    @api.model
    def populate_selectable_items(self, plink):
        my_product = plink.product_id
        my_categ = my_product.product_tmpl_id.categ_id
        if my_categ and my_categ.billable_item_model_id:
            my_billable_item_model = \
                my_categ.billable_item_model_id.sudo().model
            my_billable_item_table = \
                my_billable_item_model.replace('.', '_')
            partner_id_field = 'partner_id'
            quantity_field = ''
            if (self.env['account.billable.item'].
               inherits_from_account_billable_item(my_billable_item_model)):
                partner_id_field = \
                    self.env[my_billable_item_model]._billing_partner_id_name
                quantity_field = \
                    self.env[my_billable_item_model]._billing_quantity_name
            else:
                quantity_field = my_categ.billable_item_quantity_field
            aux_fields_insert, aux_fields_select = self._get_aux_fields(my_categ)
            sql_insert = """INSERT INTO account_selectable_item
            (id, create_uid, write_uid, create_date, write_date,
            productlink_id, billable_item_model, billable_item_res_id,
            partner_id, quantity, selected"""
            if aux_fields_insert:
                sql_insert = sql_insert + """, """ + aux_fields_insert
            sql_insert = sql_insert + """) """
            sql_insert = sql_insert + """SELECT nextval
            ('account_selectable_item_id_seq'),
            %s, %s, now(), now(),
            %s, %s, bt.id, bt.""" + partner_id_field
            if not quantity_field:
                sql_insert = sql_insert + """, 1"""
            else:
                sql_insert = sql_insert + """, bt.""" + quantity_field
            sql_insert = sql_insert + """, TRUE"""
            if aux_fields_select:
                sql_insert = sql_insert + """, """ + aux_fields_select
            sql_insert = sql_insert + """ FROM """ + my_billable_item_table + """ bt
            INNER JOIN res_partner rp ON bt.""" + partner_id_field + """ =
            rp.id WHERE rp.active"""
            if (self.env['account.billable.item'].exists_active_field(
               my_billable_item_model)):
                sql_insert = sql_insert + ' AND bt.active'
            if plink.billable_item_domain:
                sql_insert = sql_insert + ' AND ' + plink.billable_item_domain
            try:
                self.env.cr.savepoint()
                self.env.cr.execute(
                    sql_insert, (self.env.user.id, self.env.user.id, plink.id,
                                 my_billable_item_model))
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                raise exceptions.UserError(_('Error updating records:') +
                                           ' ' + str(e))

    @api.model
    def _get_aux_fields(self, category):
        aux_fields_insert = ''
        aux_fields_select = ''
        if category.aux_01_char_field:
            aux_fields_insert = aux_fields_insert + ', aux_01_char'
            aux_fields_select = (aux_fields_select + ', '
                                 + category.aux_01_char_field)
        if category.aux_01_int_field:
            aux_fields_insert = aux_fields_insert + ', aux_01_int'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_01_int_field)
        if category.aux_01_float_field:
            aux_fields_insert = aux_fields_insert + ', aux_01_float'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_01_float_field)
        if category.aux_01_bool_field:
            aux_fields_insert = aux_fields_insert + ', aux_01_bool'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_01_bool_field)
        if category.aux_02_char_field:
            aux_fields_insert = aux_fields_insert + ', aux_02_char'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_02_char_field)
        if category.aux_02_int_field:
            aux_fields_insert = aux_fields_insert + ', aux_02_int'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_02_int_field)
        if category.aux_02_float_field:
            aux_fields_insert = aux_fields_insert + ', aux_02_float'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_02_float_field)
        if category.aux_02_bool_field:
            aux_fields_insert = aux_fields_insert + ', aux_02_bool'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_02_bool_field)
        if category.aux_03_char_field:
            aux_fields_insert = aux_fields_insert + ', aux_03_char'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_03_char_field)
        if category.aux_03_int_field:
            aux_fields_insert = aux_fields_insert + ', aux_03_int'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_03_int_field)
        if category.aux_03_float_field:
            aux_fields_insert = aux_fields_insert + ', aux_03_float'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_03_float_field)
        if category.aux_03_bool_field:
            aux_fields_insert = aux_fields_insert + ', aux_03_bool'
            aux_fields_select = (aux_fields_select + ', ' +
                                 category.aux_03_bool_field)
        if aux_fields_select and aux_fields_select:
            aux_fields_insert = aux_fields_insert[2:]
            aux_fields_select = aux_fields_select[2:]
        return aux_fields_insert, aux_fields_select

    def update_populated(self):
        self.ensure_one
        populated = False
        self.env.cr.execute("""SELECT count(*) FROM account_selectable_item
        WHERE productlink_id = %s AND selected""", (self.id,))
        query_results = self.env.cr.dictfetchall()
        if query_results and query_results[0].get('count') is not None:
            populated = query_results[0].get('count') > 0
        self.write({'populated': populated})


class AccountInvoicesetProgress(models.Model):
    _name = 'account.invoiceset.progress'
    _description = ('Auxiliary model for the progress bar of  the invoice-set'
                    'calculation')

    invoiceset_id = fields.Many2one(
        string='Invoice Set',
        comodel_name='account.invoiceset',
        index=True,
        readonly=True,)

    invoice_generation_progress = fields.Float(
        string='Percentage of progress during invoice generation',
        default=0,
        readonly=True,)
