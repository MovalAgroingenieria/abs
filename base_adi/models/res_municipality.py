# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api, exceptions, _


class ResMunicipality(models.Model):
    _name = 'res.municipality'
    _description = 'Municipality'
    _inherit = ['simple.model', 'polygon.model', ]
    _order = 'province_id, name'

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
        string='Municipality',
        required=True,
        translate=True,)

    province_id = fields.Many2one(
        string='Province',
        comodel_name='res.province',
        required=True,
        index=True,
        ondelete='restrict',)

    region_id = fields.Many2one(
        string='Region',
        comodel_name='res.region',
        store=True,
        index=True,
        compute='_compute_region_id',)

    place_ids = fields.One2many(
        string='Places',
        comodel_name='res.place',
        inverse_name='municipality_id',)

    number_of_places = fields.Integer(
        string='Number of places',
        compute='_compute_number_of_places',)

    _sql_constraints = [
        ('name_unique',
         'CHECK(TRUE)',
         'Existing Code (NOT).'),
        ]

    @api.constrains('alphanum_code', 'province_id')
    def _check_alphanum_province_code(self):
        for record in self:
            if record.alphanum_code and record.province_id:
                other_municipality = self.env['res.municipality'].search(
                    [('id', '!=', record.id),
                     ('province_id', '=', record.province_id.id),
                     ('alphanum_code', '=', record.alphanum_code)])
                if other_municipality:
                    raise exceptions.ValidationError(_(
                        'There is already another municipality on this '
                        'province with the same name.'))

    @api.depends('province_id', 'province_id.region_id')
    def _compute_region_id(self):
        for record in self:
            region_id = None
            if record.province_id:
                region_id = record.province_id.region_id
            record.region_id = region_id

    def _compute_number_of_places(self):
        for record in self:
            number_of_places = 0
            self.env.cr.execute('SELECT count(*) FROM res_place '
                                'WHERE municipality_id=%s', tuple((record.id,)))
            query_results = self.env.cr.dictfetchall()
            if (query_results and
               query_results[0].get('count') is not None):
                number_of_places = \
                    query_results[0].get('count')
            record.number_of_places = number_of_places

    def name_get(self):
        resp = []
        add_province = \
            self.env.context.get('municipality_with_province', False)
        for record in self:
            name = record.alphanum_code
            if add_province:
                name = name + ' (' + record.province_id.alphanum_code + ')'
            resp.append((record.id, name))
        return resp

    def action_show_places(self):
        self.ensure_one()
        current_municipality = self
        id_tree_view = self.sudo().env.ref(
            'base_adi.res_place_view_tree').id
        id_form_view = self.sudo().env.ref(
            'base_adi.res_place_view_form').id
        search_view = self.sudo().env.ref(
            'base_adi.res_place_view_search')
        act_window = {
            'type': 'ir.actions.act_window',
            'name': _('Places'),
            'res_model': 'res.place',
            'view_mode': 'tree,form',
            'views': [(id_tree_view, 'tree'), (id_form_view, 'form')],
            'search_view_id': (search_view.id, search_view.name),
            'target': 'current',
            'domain': [('municipality_id', '=', current_municipality.id)],
            'context': {'default_municipality_id': current_municipality.id, }
            }
        return act_window
