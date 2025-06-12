# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class AccountInvoiceset(models.Model):
    _name = 'account.invoiceset'
    _description = 'Invoice Set'
    _inherit = ['simple.model', ]

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
        required=True,
    )

    description = fields.Char(
        string='Description of invoice set',
        required=True,
        translate=True,
    )

    # New fields...
