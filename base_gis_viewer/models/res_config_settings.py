# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aerial_image_wmsbase_url = fields.Char(
        related="company_id.aerial_image_wmsbase_url", readonly=False
    )
    aerial_image_wmsbase_layers = fields.Char(
        related="company_id.aerial_image_wmsbase_layers", readonly=False
    )
    aerial_image_height = fields.Integer(
        related="company_id.aerial_image_height", readonly=False
    )
    aerial_image_zoom = fields.Float(
        related="company_id.aerial_image_zoom",
        readonly=False,
        digits=(32, 4),
    )
    gis_viewer_url = fields.Char(related="company_id.gis_viewer_url", readonly=False)
    gis_viewer_username = fields.Char(
        related="company_id.gis_viewer_username", readonly=False
    )
    gis_viewer_password = fields.Char(
        related="company_id.gis_viewer_password", readonly=False
    )
    gis_viewer_cipher_key = fields.Char(
        related="company_id.gis_viewer_cipher_key", readonly=False
    )
    gis_viewer_epsg = fields.Integer(
        related="company_id.gis_viewer_epsg", readonly=False
    )
    gis_viewer_previs_additional_args = fields.Char(
        related="company_id.gis_viewer_previs_additional_args",
        readonly=False,
    )

    def set_values(self):
        self.ensure_one()
        prev_epsg = int(self.company_id.gis_viewer_epsg or 0)

        res = super().set_values()

        new_epsg = int(self.company_id.gis_viewer_epsg or 0)
        if prev_epsg and new_epsg and prev_epsg != new_epsg:
            self._on_gis_epsg_changed(prev_epsg, new_epsg)

        return res

    def _on_gis_epsg_changed(self, old_epsg, new_epsg):
        """Hook for modules that need to reproject PostGIS layers."""
        _ = (old_epsg, new_epsg)
