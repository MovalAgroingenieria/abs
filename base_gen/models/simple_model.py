# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from odoo import api, exceptions, fields, models


class SimpleModel(models.AbstractModel):
    _name = "simple.model"
    _description = "Simple Model"
    _order = "name"

    # -------------------------- Model-level settings --------------------------
    # Public flags/limits to avoid protected-access warnings
    MAX_SIZE_NAME_FIELD = 100  # storage/display cap for name/alphanum
    MAX_SIZE_CHAR_FIELD = 255  # general Char cap

    size_name = 30  # UI width for codes in forms
    size_description = 75  # UI width for description

    set_num_code = False  # numeric codes mode
    set_alphanum_code_to_lowercase = False
    set_alphanum_code_to_uppercase = False

    minlength = 0  # 0 = ignore
    maxlength = 0

    sequence_for_codes = ""  # ir.config_parameter key → ir.sequence id
    allowed_blanks_in_code = True

    # ------------------------------- Defaults ---------------------------------

    def _sequence_preview_next(self, sequence):
        """Return a human preview of the next value without consuming it."""
        # Accessing current date_range is the official way; it's a protected API,
        # so we scope-disable the warning for this single use.
        current = (
            sequence._get_current_sequence().number_next_actual
        )  # pylint: disable=protected-access
        return sequence.get_next_char(current)

    def _default_alphanum_code(self):
        """Return the next code from the configured ir.sequence (if any)."""
        if not self.sequence_for_codes:
            return ""
        sequence = self._get_sequence(self.sequence_for_codes)
        if not sequence:
            return ""
        return self._sequence_preview_next(sequence)

    def _default_num_code(self):
        """Return the next integer code when numeric codes are enabled."""
        if not self.set_num_code:
            return 0
        last = self.search([], limit=1, order="num_code desc")
        return (last.num_code + 1) if last else 1

    # --------------------------------- Fields ---------------------------------

    alphanum_code = fields.Char(
        string="Code (alphanumeric)",
        size=MAX_SIZE_NAME_FIELD,
        default=lambda self: self._default_alphanum_code(),  # E8148
        index=True,
    )

    num_code = fields.Integer(
        string="Code (numeric)",
        default=lambda self: self._default_num_code(),  # E8148
        index=True,
    )

    description = fields.Char(  # string is redundant → removed (W8113)
        size=MAX_SIZE_CHAR_FIELD,
        index=True,
    )

    name = fields.Char(
        string="Code (name)",
        size=MAX_SIZE_NAME_FIELD,
        store=True,
        index=True,
        compute="_compute_name",
    )

    notes = fields.Html(string="Internal Notes")

    _sql_constraints = [
        ("name_unique", "UNIQUE (name)", "Existing Code."),
        (
            "name_not_null",
            "CHECK (alphanum_code IS NOT NULL OR num_code > 0)",
            "A valid code is required.",
        ),
        (
            "description_not_null",
            "CHECK (description IS NOT NULL OR alphanum_code IS NOT NULL)",
            "The description is required.",
        ),
    ]

    # ------------------------------- Computes ---------------------------------

    @api.depends("alphanum_code", "num_code")
    def _compute_name(self):
        """Build 'name' from alphanum or numeric code based on flags."""
        for record in self:
            if record.set_num_code:
                padded = str(record.num_code or 0).zfill(record.size_name)
                record.name = padded
            else:
                record.name = (record.alphanum_code or "")[: record.size_name]

    def _compute_display_name(self):
        """Odoo 18: replace name_get (E8146)."""
        for record in self:
            if record.set_num_code:
                desc = record.description or ""
                record.display_name = f"{desc} [{record.num_code}]"
            else:
                record.display_name = record.alphanum_code or ""

    # ------------------------------ Constraints -------------------------------

    @api.constrains("alphanum_code")
    def _check_alphanum_code(self):
        """Validate blanks and length ranges for alphanumeric codes."""
        for record in self:
            code = record.alphanum_code or ""
            if (not record.allowed_blanks_in_code) and (" " in code):
                raise exceptions.ValidationError(
                    record.env._(
                        "It is not possible to insert blank spaces in the code."
                    )
                )
            if record.minlength and code and len(code) < record.minlength:
                raise exceptions.ValidationError(
                    record.env._(
                        "Minimum number of characters allowed for the code: %s.",
                        record.minlength,
                    )
                )
            if record.maxlength and code and len(code) > record.maxlength:
                raise exceptions.ValidationError(
                    record.env._(
                        "Maximum number of characters allowed for the code: %s.",
                        record.maxlength,
                    )
                )

    # --------------------------------- Names ----------------------------------

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Search by description (numeric mode) or alphanum_code (default)."""
        domain = list(args or [])

        if name:
            field_name = "description" if self._set_num_code else "alphanum_code"
            domain = [(field_name, operator, name)] + domain

        # Use search_fetch to avoid extra reads (v17+)
        recs = self.search_fetch(
            domain, ["display_name"], limit=limit, order="display_name"
        )
        return [(rec.id, rec.display_name) for rec in recs]

    # --------------------------------- CRUD -----------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Normalize inputs and keep the sequence in sync when used."""
        vals_list = list(vals_list)  # ensure mutability
        seq_bumps = 0
        sequence = (
            self._get_sequence(self.sequence_for_codes)
            if self.sequence_for_codes
            else None
        )

        for vals in vals_list:
            # Normalize alphanumeric code
            code = vals.get("alphanum_code")
            if code:
                if sequence:
                    # If provided code equals the "next" preview, advance sequence
                    preview = self._sequence_preview_next(sequence)
                    if preview == code:
                        sequence.next_by_id()
                else:
                    vals["alphanum_code"] = self._process_alphanum_code(code)
            else:
                # If field is readonly and not present, count for later bumps
                if sequence:
                    seq_bumps += 1

            # Normalize description
            desc = vals.get("description")
            if desc:
                vals["description"] = self._process_description(desc)

            # Hook for custom field massaging
            self._process_vals(vals)

        records = super().create(vals_list)

        # Advance the sequence for the autogenerated codes
        if seq_bumps and sequence:
            for _i in range(seq_bumps):
                sequence.next_by_id()

        return records

    def write(self, vals):
        """Normalize inputs on write."""
        code = vals.get("alphanum_code")
        if code:
            vals["alphanum_code"] = self._process_alphanum_code(code)

        desc = vals.get("description")
        if desc:
            vals["description"] = self._process_description(desc)

        self._process_vals(vals)
        return super().write(vals)

    # ------------------------------- Utilities --------------------------------

    def _get_sequence(self, param_name):
        """Return an ir.sequence record configured by ir.config_parameter."""
        seq_id = self.env["ir.config_parameter"].sudo().get_param(param_name)
        if not seq_id:
            return None
        try:
            seq_id_int = int(seq_id)
        except (TypeError, ValueError):
            return None
        if seq_id_int <= 0:
            return None
        seq = self.env["ir.sequence"].browse(seq_id_int).exists()
        if not seq:
            seq = self.env["ir.sequence"].search([("id", "=", seq_id_int)], limit=1)
        return seq or None

    def _process_alphanum_code(self, value: str) -> str:
        """Trim to UI length and apply lower/upper transforms if enabled."""
        resp = (value or "")[: self.size_name]
        if self.set_alphanum_code_to_lowercase:
            resp = resp.lower()
        if self.set_alphanum_code_to_uppercase:
            resp = resp.upper()
        return resp

    def _process_description(self, value: str) -> str:
        """Trim description to UI length."""
        return (value or "")[: self.size_description]

    # Hook: override to adjust values before create/write
    # pylint: disable=unused-argument
    def _process_vals(self, vals):  # noqa: ARG002 (unused-argument)
        """Override in children to massage vals before persistence."""
        # Intentionally does nothing; override in subclasses.
        return None
