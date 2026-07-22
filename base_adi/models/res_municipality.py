# 2024-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResMunicipality(models.Model):
    _name = "res.municipality"
    _description = "Municipality"
    _inherit = [
        "simple.model",
        "polygon.model",
    ]
    _order = "province_id, name"

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
        string="Municipality",
        required=True,
        translate=True,
    )

    province_id = fields.Many2one(
        comodel_name="res.province",
        required=True,
        index=True,
        ondelete="restrict",
    )

    region_id = fields.Many2one(
        string="Region",
        comodel_name="res.admregion",
        related="province_id.region_id",
        store=True,
        index=True,
        readonly=True,
    )

    place_ids = fields.One2many(
        string="Places",
        comodel_name="res.place",
        inverse_name="municipality_id",
    )

    number_of_places = fields.Integer(
        string="Number of places",
        compute="_compute_number_of_places",
    )

    _sql_constraints = [
        ("name_unique", "CHECK(TRUE)", "Existing Code (NOT)."),
    ]

    @api.constrains("alphanum_code", "province_id")
    def _check_alphanum_province_code(self):
        for record in self:
            if not record.alphanum_code or not record.province_id:
                continue
            duplicate = self.search(
                [
                    ("id", "!=", record.id),
                    ("province_id", "=", record.province_id.id),
                    ("alphanum_code", "=", record.alphanum_code),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    self.env._(
                        "There is already another municipality in this province "
                        "with the same name."
                    )
                )

    def _compute_number_of_places(self):
        grouped = self.env["res.place"].read_group(
            [("municipality_id", "in", self.ids)],
            ["municipality_id"],
            ["municipality_id"],
        )
        count_by_municipality = {
            item["municipality_id"][0]: item["municipality_id_count"]
            for item in grouped
            if item.get("municipality_id")
        }
        for record in self:
            record.number_of_places = count_by_municipality.get(record.id, 0)

    @api.depends("alphanum_code", "province_id")
    def _compute_display_name(self):
        add_province = self.env.context.get("municipality_with_province", False)
        for record in self:
            name = record.alphanum_code
            if add_province and record.province_id:
                name = f"{name} ({record.province_id.alphanum_code})"
            record.display_name = name

    def action_show_places(self):
        self.ensure_one()
        tree_view = self.env.ref(
            "base_adi.res_place_view_list", raise_if_not_found=False
        )
        form_view = self.env.ref(
            "base_adi.res_place_view_form", raise_if_not_found=False
        )
        search_view = self.env.ref(
            "base_adi.res_place_view_search", raise_if_not_found=False
        )

        views = []
        if tree_view:
            views.append((tree_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))

        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Places"),
            "res_model": "res.place",
            "view_mode": "list,form",
            "views": views or [(False, "list"), (False, "form")],
            "search_view_id": search_view.id if search_view else False,
            "target": "current",
            "domain": [("municipality_id", "=", self.id)],
            "context": {"default_municipality_id": self.id},
        }
