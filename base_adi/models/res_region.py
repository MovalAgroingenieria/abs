# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, _


class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Region'
    _inherit = ['simple.model', 'polygon.model', ]

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
        string='Region',
        required=True,
        translate=True,)

    flag_image_256 = fields.Image(
        string='Flag (256 x 172)',
        max_width=256,
        max_height=172,)

    flag_image_128 = fields.Image(
        string='Flag (128 x 86)',
        max_width=128,
        max_height=86,
        store=True,
        related='flag_image_256',)

    flag_image_64 = fields.Image(
        string='Flag (64 x 43)',
        max_width=64,
        max_height=43,
        store=True,
        related='flag_image_256',)

    province_ids = fields.One2many(
        string='Provinces',
        comodel_name='res.province',
        inverse_name='region_id',)

    number_of_provinces = fields.Integer(
        string='Number of provinces',
        compute='_compute_number_of_provinces',)

    def _compute_number_of_provinces(self):
        for record in self:
            number_of_provinces = 0
            self.env.cr.execute('SELECT count(*) FROM res_province '
                                'WHERE region_id=%s', tuple((record.id,)))
            query_results = self.env.cr.dictfetchall()
            if (query_results and
               query_results[0].get('count') is not None):
                number_of_provinces = \
                    query_results[0].get('count')
            record.number_of_provinces = number_of_provinces

    def action_show_provinces(self):
        self.ensure_one()
        current_region = self
        id_tree_view = self.sudo().env.ref(
            'base_adi.res_province_view_tree').id
        id_form_view = self.sudo().env.ref(
            'base_adi.res_province_view_form').id
        search_view = self.sudo().env.ref(
            'base_adi.res_province_view_search')
        act_window = {
            'type': 'ir.actions.act_window',
            'name': _('Provinces'),
            'res_model': 'res.province',
            'view_mode': 'tree,form',
            'views': [(id_tree_view, 'tree'), (id_form_view, 'form')],
            'search_view_id': (search_view.id, search_view.name),
            'target': 'current',
            'domain': [('region_id', '=', current_region.id)],
            'context': {'default_region_id': current_region.id, }
            }
        return act_window
