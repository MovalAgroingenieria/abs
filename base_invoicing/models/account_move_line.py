# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = ['account.move.line']

    invoiceset_id = fields.Many2one(
        string='Invoice Set',
        comodel_name='account.invoiceset',
        store=True,
        index=True,
        compute='_compute_invoiceset_id',)

    categ_id = fields.Many2one(
        string='Product Category',
        comodel_name='product.category',
        store=True,
        compute='_compute_categ_id',)

    invoice_user_id = fields.Many2one(
        string='Sales Person',
        comodel_name='res.users',
        store=True,
        compute='_compute_invoice_user_id',)

    price_taxes = fields.Monetary(
        string='Tax',
        store=True,
        compute='_compute_price_taxes',
        currency_field='currency_id',)

    billable_item_model = fields.Char(
        string='Billable item model: name',)

    billable_item_res_id = fields.Many2oneReference(
        string='Billable item model: reference',
        model_field='billable_item_model',)

    @api.depends('move_id')
    def _compute_invoiceset_id(self):
        for record in self:
            invoiceset_id = None
            if record.move_id and record.move_id.invoiceset_id:
                invoiceset_id = record.move_id.invoiceset_id
            record.invoiceset_id = invoiceset_id

    @api.depends('product_id')
    def _compute_categ_id(self):
        for record in self:
            categ_id = None
            if (record.product_id and
               record.product_id.product_tmpl_id.categ_id):
                categ_id = record.product_id.product_tmpl_id.categ_id
            record.categ_id = categ_id

    @api.depends('move_id')
    def _compute_invoice_user_id(self):
        for record in self:
            invoice_user_id = None
            if record.move_id and record.move_id.invoice_user_id:
                invoice_user_id = record.move_id.invoice_user_id
            record.invoice_user_id = invoice_user_id

    @api.depends('price_total')
    def _compute_price_taxes(self):
        for record in self:
            price_taxes = 0
            if record.credit > 0:
                price_taxes = record.price_total - record.price_subtotal
            record.price_taxes = price_taxes

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if ('billable_item_model' in vals and
               'billable_item_res_id' in vals):
                billable_item_model = vals['billable_item_model']
                billable_item_res_id = vals['billable_item_res_id']
                if billable_item_model and billable_item_res_id:
                    with_abstract_model = \
                        (self.env['account.billable.item'].
                         inherits_from_account_billable_item(
                            billable_item_model))
                    if (billable_item_model and billable_item_res_id and
                       with_abstract_model):
                        my_billable_item = \
                            self.env[billable_item_model].sudo().browse(
                                billable_item_res_id).exists()
                        if my_billable_item:
                            my_billable_item.number_of_invoices = \
                                my_billable_item.number_of_invoices + 1
        move_lines = super(AccountMoveLine, self).create(vals_list)
        return move_lines

    def unlink(self):
        if not self.ids:
            return super(AccountMoveLine, self).unlink()
        self.env.cr.execute(
            """
            SELECT id, billable_item_model, billable_item_res_id
              FROM account_move_line
             WHERE id IN %s
            """,
            (tuple(self.ids),)
        )
        move_line_data = {
            row['id']: row for row in self.env.cr.dictfetchall()
        }
        for record in self:
            line_data = move_line_data.get(record.id, {})
            billable_item_model = line_data.get('billable_item_model')
            billable_item_res_id = line_data.get('billable_item_res_id')
            if billable_item_model and billable_item_res_id:
                with_abstract_model = \
                    (self.env['account.billable.item'].
                     inherits_from_account_billable_item(billable_item_model))
                if with_abstract_model:
                    # Ensure that the billable item still exists, as it could
                    # have been deleted after the move line was created
                    # (partnerlink)
                    my_billable_item = \
                        self.env[billable_item_model].sudo().browse(
                            billable_item_res_id).exists()
                    if my_billable_item:
                        my_billable_item.number_of_invoices = \
                            max(my_billable_item.number_of_invoices - 1, 0)
        res = super(AccountMoveLine, self).unlink()
        return res
