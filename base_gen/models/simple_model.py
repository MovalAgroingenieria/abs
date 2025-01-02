# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, exceptions, fields, models, _


class SimpleModel(models.AbstractModel):
    _name = 'simple.model'
    _description = 'Simple Model'
    _order = 'name'

    # Size of the "name" and "alphanum_code" fields, in the model.
    MAX_SIZE_NAME_FIELD = 100

    # Size of the fields of char type, in the model.
    MAX_SIZE_CHAR_FIELD = 255

    # Size of "name" and "alphanum_code" fields, in the form view.
    _size_name = 30

    # Size of "description" field, in the form view.
    _size_description = 75

    # Are the codes numeric values?
    _set_num_code = False

    # If the code is an alphanumeric value, convert it to lowercase?
    _set_alphanum_code_to_lowercase = False

    # If the code is an alphanumeric value, convert it to uppercase?
    _set_alphanum_code_to_uppercase = False

    # Minimum length allowed for alphanumeric codes (ignore if 0).
    _minlength = 0

    # Maximum length allowed for alphanumeric codes (ignore if 0).
    _maxlength = 0

    # Name of a possible sequence to generate alphanumeric codes (parameter,
    # registered in "ir.config.parameter").
    _sequence_for_codes = ''

    # Possible condition for alphanumeric codes: is it possible to enter
    # blank spaces in the code?
    _allowed_blanks_in_code = True

    def _default_alphanum_code(self):
        resp = ''
        if self._sequence_for_codes:
            sequence = self._get_sequence(self._sequence_for_codes)
            if sequence:
                number_next_actual = \
                    sequence._get_current_sequence().number_next_actual
                resp = sequence.get_next_char(number_next_actual)
        return resp

    def _default_num_code(self):
        resp = 0
        if self._set_num_code:
            records = self.search([], limit=1,
                                  order='num_code desc')
            if records:
                resp = records[0].num_code + 1
            else:
                resp = 1
            return resp
        return resp

    alphanum_code = fields.Char(
        string='Code (alphanumeric value)',
        size=MAX_SIZE_NAME_FIELD,
        default=_default_alphanum_code,
        index=True,)

    num_code = fields.Integer(
        string='Code (numeric value)',
        default=_default_num_code,
        index=True,)

    description = fields.Char(
        string='Description',
        size=MAX_SIZE_CHAR_FIELD,
        index=True,)

    name = fields.Char(
        string='Code (name)',
        size=MAX_SIZE_NAME_FIELD,
        store=True,
        index=True,
        compute='_compute_name',)

    notes = fields.Html(
        string='Internal Notes',)

    _sql_constraints = [
        ('name_unique',
         'UNIQUE (name)',
         'Existing Code.'),
        ('name_not_null',
         'CHECK (alphanum_code IS NOT NULL OR num_code > 0)',
         'A valid code is required.'),
        ('description_not_null',
         'CHECK (description IS NOT NULL OR alphanum_code IS NOT NULL)',
         'The description is required.'),
        ]

    @api.depends('alphanum_code', 'num_code')
    def _compute_name(self):
        for record in self:
            name = record.alphanum_code
            if self._set_num_code:
                name = '0'.zfill(self._size_name)
                if record.num_code:
                    name = str(record.num_code).zfill(self._size_name)
            record.name = name

    @api.constrains('alphanum_code')
    def _check_alphanum_code(self):
        for record in self:
            if ((not self._allowed_blanks_in_code) and
               record.alphanum_code.find(' ') != -1):
                raise exceptions.ValidationError(_(
                    'It is not possible insert blank spaces in the code.'))
            if (self._minlength and record.alphanum_code and
               len(record.alphanum_code) < self._minlength):
                raise exceptions.ValidationError(_(
                    'Minimum number of characters allowed for te code: ') +
                    str(self._minlength) + '.')
            if (self._maxlength and record.alphanum_code and
               len(record.alphanum_code) > self._maxlength):
                raise exceptions.ValidationError(_(
                    'Maximum number of characters allowed for te code: ') +
                    str(self._maxlength) + '.')

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if self._set_num_code:
            records = self.search(
                [('description', 'ilike', name)] + args, limit=limit)
        else:
            records = self.search(
                [('alphanum_code', 'ilike', name)] + args, limit=limit)
        return records.name_get()

    def name_get(self):
        resp = []
        for record in self:
            name = record.alphanum_code
            if self._set_num_code:
                description = ''
                if record.description:
                    description = record.description
                name = description + ' [' + str(record.num_code) + ']'
            resp.append((record.id, name))
        return resp

    @api.model_create_multi
    def create(self, vals_list):
        value_to_add_to_sequence = 0
        sequence = None
        if self._sequence_for_codes:
            sequence = self._get_sequence(self._sequence_for_codes)
        for vals in vals_list:
            if 'alphanum_code' in vals and vals['alphanum_code']:
                if sequence:
                    number_next_actual = \
                        sequence._get_current_sequence().number_next_actual
                    next_code = sequence.get_next_char(number_next_actual)
                    if next_code == vals['alphanum_code']:
                        sequence.next_by_id()
                else:
                    original_alphanum_code = vals['alphanum_code']
                    final_alphanum_code = self._process_alphanum_code(
                        original_alphanum_code)
                    vals['alphanum_code'] = final_alphanum_code
            else:  # if "alphanum_code" is read-only, then it is not in vals
                if sequence:
                    value_to_add_to_sequence = value_to_add_to_sequence + 1
            if 'description' in vals and vals['description']:
                original_description = vals['description']
                final_description = self._process_description(
                    original_description)
                vals['description'] = final_description
            self._process_vals(vals)
        records = super(SimpleModel, self).create(vals_list)
        if value_to_add_to_sequence > 0 and sequence:
            i = 0
            while i < value_to_add_to_sequence:
                sequence.next_by_id()
                i = i + 1
        return records

    def write(self, vals):
        if 'alphanum_code' in vals and vals['alphanum_code']:
            original_alphanum_code = vals['alphanum_code']
            final_alphanum_code = self._process_alphanum_code(
                original_alphanum_code)
            vals['alphanum_code'] = final_alphanum_code
        if 'description' in vals and vals['description']:
            original_description = vals['description']
            final_description = self._process_description(
                original_description)
            vals['description'] = final_description
        self._process_vals(vals)
        resp = super(SimpleModel, self).write(vals)
        return resp

    def _get_sequence(self, param_name):
        resp = None
        sequence_id = \
            self.env['ir.config_parameter'].sudo().get_param(param_name)
        if sequence_id:
            sequence_id = int(sequence_id) if sequence_id.isdigit() else 0
            if sequence_id > 0:
                resp = self.env['ir.sequence'].search(
                    [('id', '=', sequence_id)])
                if resp:
                    resp = resp[0]
        return resp

    def _process_alphanum_code(self, value):
        resp = value
        if len(resp) > self._size_name:
            resp = resp[0:self._size_name]
        if self._set_alphanum_code_to_lowercase:
            resp = resp.lower()
        if self._set_alphanum_code_to_uppercase:
            resp = resp.upper()
        return resp

    def _process_description(self, value):
        resp = value
        if len(resp) > self._size_description:
            resp = resp[0:self._size_description]
        return resp

    # Hook: This method can be called to change some values of the
    # "vals" dictionary, before saving a register.
    def _process_vals(self, vals):
        return None
