# 2024-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import _, fields, models


class ResAdmregion(models.Model):
    _name = "res.admregion"
    _description = "Region"
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
        string="Region",
        required=True,
        translate=True,
    )

    flag_image_256 = fields.Image(
        string="Flag (256 x 172)",
        max_width=256,
        max_height=172,
    )

    flag_image_128 = fields.Image(
        string="Flag (128 x 86)",
        max_width=128,
        max_height=86,
        related="flag_image_256",
        store=True,
        readonly=True,
    )

    flag_image_64 = fields.Image(
        string="Flag (64 x 43)",
        max_width=64,
        max_height=43,
        related="flag_image_256",
        store=True,
        readonly=True,
    )

    province_ids = fields.One2many(
        string="Provinces",
        comodel_name="res.province",
        inverse_name="region_id",
    )

    number_of_provinces = fields.Integer(
        string="Number of provinces",
        compute="_compute_number_of_provinces",
    )

    def _compute_number_of_provinces(self):
        grouped = self.env["res.province"].read_group(
            [("region_id", "in", self.ids)],
            ["region_id"],
            ["region_id"],
        )
        count_by_region = {
            item["region_id"][0]: item["region_id_count"]
            for item in grouped
            if item.get("region_id")
        }
        for record in self:
            record.number_of_provinces = count_by_region.get(record.id, 0)

    def action_show_provinces(self):
        self.ensure_one()
        tree_view = self.env.ref(
            "base_adi.res_province_view_tree", raise_if_not_found=False
        )
        form_view = self.env.ref(
            "base_adi.res_province_view_form", raise_if_not_found=False
        )
        search_view = self.env.ref(
            "base_adi.res_province_view_search", raise_if_not_found=False
        )

        views = []
        if tree_view:
            views.append((tree_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))

        return {
            "type": "ir.actions.act_window",
            "name": _("Provinces"),
            "res_model": "res.province",
            "view_mode": "list,form",
            "views": views or [(False, "list"), (False, "form")],
            "search_view_id": search_view.id if search_view else False,
            "target": "current",
            "domain": [("region_id", "=", self.id)],
            "context": {"default_region_id": self.id},
        }
