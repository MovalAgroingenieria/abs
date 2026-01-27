# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import _, fields, models


class ResProvince(models.Model):
    _name = "res.province"
    _description = "Province"
    _inherit = [
        "simple.model",
        "polygon.model",
    ]

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
        string="Province",
        required=True,
        translate=True,
    )

    region_id = fields.Many2one(
        string="Region",
        comodel_name="res.admregion",
        required=True,
        index=True,
        ondelete="restrict",
    )

    municipality_ids = fields.One2many(
        string="Municipalities",
        comodel_name="res.municipality",
        inverse_name="province_id",
    )

    number_of_municipalities = fields.Integer(
        string="Number of municipalities",
        compute="_compute_number_of_municipalities",
    )

    def _compute_number_of_municipalities(self):
        grouped = self.env["res.municipality"].read_group(
            [("province_id", "in", self.ids)],
            ["province_id"],
            ["province_id"],
        )
        count_by_province = {
            item["province_id"][0]: item["province_id_count"]
            for item in grouped
            if item.get("province_id")
        }
        for record in self:
            record.number_of_municipalities = count_by_province.get(record.id, 0)

    def action_show_municipalities(self):
        self.ensure_one()
        tree_view = self.env.ref("base_adi.res_municipality_view_tree", raise_if_not_found=False)
        form_view = self.env.ref("base_adi.res_municipality_view_form", raise_if_not_found=False)
        search_view = self.env.ref("base_adi.res_municipality_view_search", raise_if_not_found=False)

        views = []
        if tree_view:
            views.append((tree_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))

        return {
            "type": "ir.actions.act_window",
            "name": _("Municipalities"),
            "res_model": "res.municipality",
            "view_mode": "list,form",
            "views": views or [(False, "list"), (False, "form")],
            "search_view_id": search_view.id if search_view else False,
            "target": "current",
            "domain": [("province_id", "=", self.id)],
            "context": {"default_province_id": self.id},
        }
