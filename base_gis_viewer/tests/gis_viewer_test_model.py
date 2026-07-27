# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class GisViewerTestModel(models.Model):
    _name = "gis.viewer.test.model"
    _description = "GIS Viewer test model"
    _inherit = "gis.viewer"
    _gis_mapped_field = "mapped_to_polygon"

    name = fields.Char(required=True)
    mapped_to_polygon = fields.Boolean(default=True)
    geom_ewkt = fields.Char()

    def extract_bounding_box(self, _ewkt, force_square_shape=False):
        _ = force_square_shape  # required by gis.viewer API, unused in this test stub
        bbox = (0.0, 0.0, 10.0, 10.0)
        return 4326, bbox
