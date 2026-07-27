# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    aerial_image_wmsbase_url = fields.Char(
        string="WMS of the base image: URL", size=255
    )
    aerial_image_wmsbase_layers = fields.Char(
        string="WMS of the base image: Layers", size=255
    )
    aerial_image_height = fields.Integer(
        string="WMS Services: Height of the images",
        default=512,
    )
    aerial_image_zoom = fields.Float(
        string="WMS Services: Zoom",
        digits=(32, 4),
        default=1.2,
    )
    gis_viewer_url = fields.Char(string="GIS Viewer: URL", size=255)
    gis_viewer_username = fields.Char(
        string="GIS Viewer: User name for the technical mode", size=255
    )
    gis_viewer_password = fields.Char(
        string="GIS Viewer: Password for the technical mode", size=255
    )
    gis_viewer_cipher_key = fields.Char(
        string="GIS Viewer: Cipher key for technical mode", size=255
    )
    gis_viewer_epsg = fields.Integer(
        string="GIS Viewer: Spatial Reference",
        default=25830,
    )
    gis_viewer_previs_additional_args = fields.Char(
        string="GIS Preview: Additional URL arguments", size=255
    )

    _sql_constraints = [
        (
            "aerial_image_height_ok",
            "CHECK (aerial_image_height > 0)",
            'Incorrect value of "WMS Services: Height of the images".',
        ),
        (
            "aerial_image_zoom_ok",
            "CHECK (aerial_image_zoom > 0)",
            'Incorrect value of "WMS Services: Zoom".',
        ),
        (
            "gis_viewer_epsg_ok",
            "CHECK (gis_viewer_epsg > 0)",
            'Incorrect value of "GIS Viewer: Spatial Reference".',
        ),
    ]
