# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models, _


class ResProvince(models.Model):
    _name = 'res.province'
    _description = 'Province'
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
        string='Province',
        required=True,
        translate=True,)

    region_id = fields.Many2one(
        string='Region',
        comodel_name='res.region',
        required=True,
        index=True,
        ondelete='restrict',)

    municipality_ids = fields.One2many(
        string='Municipalities',
        comodel_name='res.municipality',
        inverse_name='province_id',)

    number_of_municipalities = fields.Integer(
        string='Number of municipalities',
        compute='_compute_number_of_municipalities',)

    def _compute_number_of_municipalities(self):
        for record in self:
            number_of_municipalities = 0
            self.env.cr.execute('SELECT count(*) FROM res_municipality '
                                'WHERE province_id=%s', tuple((record.id,)))
            query_results = self.env.cr.dictfetchall()
            if (query_results and
               query_results[0].get('count') is not None):
                number_of_municipalities = \
                    query_results[0].get('count')
            record.number_of_municipalities = number_of_municipalities

    def action_show_municipalities(self):
        self.ensure_one()
        current_province = self
        id_tree_view = self.sudo().env.ref(
            'base_adi.res_municipality_view_tree').id
        id_form_view = self.sudo().env.ref(
            'base_adi.res_municipality_view_form').id
        search_view = self.sudo().env.ref(
            'base_adi.res_municipality_view_search')
        act_window = {
            'type': 'ir.actions.act_window',
            'name': _('Municipalities'),
            'res_model': 'res.municipality',
            'view_mode': 'tree,form',
            'views': [(id_tree_view, 'tree'), (id_form_view, 'form')],
            'search_view_id': (search_view.id, search_view.name),
            'target': 'current',
            'domain': [('province_id', '=', current_province.id)],
            'context': {'default_province_id': current_province.id, }
            }
        return act_window
