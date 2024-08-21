# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api


class ResPlace(models.Model):
    _name = 'res.place'
    _description = 'Place'
    _inherit = 'simple.model'
    _order = 'region_id, province_id, name'

    # Static variables inherited from "simple.model"
    _set_num_code = False
    _sequence_for_codes = ''
    _size_name = 50
    _minlength = 0
    _maxlength = 50
    _allowed_blanks_in_code = True
    _set_alphanum_code_to_lowercase = False
    _set_alphanum_code_to_uppercase = False
    _size_description = 75

    alphanum_code = fields.Char(
        string='Place',
        required=True,
        translate=True,)

    municipality_id = fields.Many2one(
        string='Municipality',
        comodel_name='res.municipality',
        required=True,
        index=True,
        ondelete='restrict',)

    province_id = fields.Many2one(
        string='Province',
        comodel_name='res.province',
        store=True,
        index=True,
        compute='_compute_province_id',)

    region_id = fields.Many2one(
        string='Region',
        comodel_name='res.region',
        store=True,
        index=True,
        compute='_compute_region_id',)

    @api.depends('municipality_id', 'municipality_id.province_id')
    def _compute_province_id(self):
        for record in self:
            province_id = None
            if record.municipality_id:
                province_id = record.municipality_id.province_id
            record.province_id = province_id

    @api.depends('province_id', 'province_id.region_id')
    def _compute_region_id(self):
        for record in self:
            region_id = None
            if record.province_id:
                region_id = record.province_id.region_id
            record.region_id = region_id
