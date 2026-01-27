# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class BaseGisPolygonTest(models.Model):
    _name = "base_gis.polygon_test"
    _description = "Polygon model test helper"
    _inherit = "polygon.model"

    name = fields.Char(required=True)

    # Keep GIS config empty so _geom_ok() is False in tests
    _gis_table = ""
    _geom_field = "geom"
    _link_field = "name"
