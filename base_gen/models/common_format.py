# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models


class CommonFormat(models.AbstractModel):
    _name = 'common.format'
    _description = 'Common functions related to format management '\
                   '(numbers, dates, etc)'

    def transform_integer_to_locale(self, integer_number, lang=False):
        resp = ''
        if not lang:
            lang = 'es_ES'
            if 'lang' in self.env.context and self.env.context['lang']:
                lang = self.env.context['lang']
        lang_model = self.env['res.lang'].search([('code', '=', lang)])
        if lang_model:
            lang_model = lang_model[0]
            thousands_sep = lang_model.thousands_sep
            resp = f"{integer_number:_}".replace('_', thousands_sep)
        return resp
