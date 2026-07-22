# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code
from odoo import api, fields, models


class ResPlace(models.Model):
    _name = "res.place"
    _description = "Place"
    _inherit = "simple.model"
    _order = "region_id, province_id, name"
    _rec_name = "alphanum_code"

    # Static variables inherited from "simple.model"
    _set_num_code = False
    _sequence_for_codes = ""
    _size_name = 50
    _minlength = 0
    _maxlength = 50
    _allowed_blanks_in_code = True
    _set_alphanum_code_to_lowercase = False
    _set_alphanum_code_to_uppercase = False
    _size_description = 75

    alphanum_code = fields.Char(
        string="Place",
        required=True,
        translate=True,
    )

    municipality_id = fields.Many2one(
        comodel_name="res.municipality",
        required=True,
        index=True,
        ondelete="restrict",
    )

    province_id = fields.Many2one(
        string="Province",
        comodel_name="res.province",
        related="municipality_id.province_id",
        store=True,
        index=True,
        readonly=True,
    )

    region_id = fields.Many2one(
        string="Region",
        comodel_name="res.admregion",
        related="province_id.region_id",
        store=True,
        index=True,
        readonly=True,
    )

    @api.depends("alphanum_code", "municipality_id.alphanum_code")
    def _compute_name(self):
        for record in self:
            name = record.alphanum_code or ""
            if record.municipality_id and record.municipality_id.alphanum_code:
                name = f"{name} ({record.municipality_id.alphanum_code})"
            record.name = name
