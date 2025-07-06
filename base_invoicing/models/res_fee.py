# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class ResFee(models.Model):
    _name = 'res.fee'
    _description = 'Fee'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['account.billable.item']

    _billing_partner_id_name = 'partner_id'
    _billing_quantity_name = ''

    partner_id = fields.Many2one(
        string='Associated Partner',
        comodel_name='res.partner',
        required=True,
        ondelete='cascade',
        auto_join=True,
        index=True,)

    partner_parent_id = fields.Many2one(
        string='Related company of partner',
        comodel_name='res.partner',
        store=True,
        compute='_compute_partner_parent_id',
        index=True, )

    partner_partner_share = fields.Boolean(
        string='Share partner of partner',
        store=True,
        compute='_compute_partner_partner_share',)

    partner_vat = fields.Char(
        string='VAT of partner',
        store=True,
        compute='_compute_partner_vat',)

    partner_email = fields.Char(
        string='Email of partner',
        store=True,
        compute='_compute_partner_email',)

    partner_phone = fields.Char(
        string='Phone of partner',
        store=True,
        compute='_compute_partner_phone',)

    partner_mobile = fields.Char(
        string='Mobile of partner',
        store=True,
        compute='_compute_partner_mobile',)

    partner_is_company = fields.Boolean(
        string='Company (y/n)',
        store=True,
        compute='_compute_partner_is_company',)

    @api.depends('partner_id', 'partner_id.parent_id')
    def _compute_partner_parent_id(self):
        for record in self:
            partner_parent_id = None
            if record.partner_id and record.partner_id.parent_id:
                partner_parent_id = record.partner_id.parent_id
            record.partner_parent_id = partner_parent_id

    @api.depends('partner_id', 'partner_id.partner_share')
    def _compute_partner_partner_share(self):
        for record in self:
            partner_partner_share = False
            if record.partner_id and record.partner_id.partner_share:
                partner_partner_share = True
            record.partner_partner_share = partner_partner_share

    @api.depends('partner_id', 'partner_id.vat')
    def _compute_partner_vat(self):
        for record in self:
            partner_vat = None
            if record.partner_id and record.partner_id.vat:
                partner_vat = record.partner_id.vat
            record.partner_vat = partner_vat

    @api.depends('partner_id', 'partner_id.email')
    def _compute_partner_email(self):
        for record in self:
            partner_email = None
            if record.partner_id and record.partner_id.email:
                partner_email = record.partner_id.email
            record.partner_email = partner_email

    @api.depends('partner_id', 'partner_id.phone')
    def _compute_partner_phone(self):
        for record in self:
            partner_phone = None
            if record.partner_id and record.partner_id.phone:
                partner_phone = record.partner_id.phone
            record.partner_phone = partner_phone

    @api.depends('partner_id', 'partner_id.mobile')
    def _compute_partner_mobile(self):
        for record in self:
            partner_mobile = None
            if record.partner_id and record.partner_id.mobile:
                partner_mobile = record.partner_id.mobile
            record.partner_mobile = partner_mobile

    @api.depends('partner_id', 'partner_id.is_company')
    def _compute_partner_is_company(self):
        for record in self:
            partner_is_company = False
            if record.partner_id and record.partner_id.is_company:
                partner_is_company = True
            record.partner_is_company = partner_is_company
