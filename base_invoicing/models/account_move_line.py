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
