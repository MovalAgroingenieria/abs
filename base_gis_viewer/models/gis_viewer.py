# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

import base64
import datetime
import logging

import pytz
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from odoo import api, fields, models
from odoo.http import request

_logger = logging.getLogger(__name__)


class GisViewer(models.AbstractModel):
    _name = "gis.viewer"
    _description = "Use of GIS viewers"

    DEFAULT_GIS_VIEWER = "https://gis.moval.es"
    DEFAULT_TZ = "Europe/Madrid"
    _param_gis_selection = ""
    _gis_mapped_field = ""

    gis_code = fields.Char(string="GIS Code", compute="_compute_gis_code")
    gis_link_public = fields.Char(
        string="GIS Link (public)", compute="_compute_gis_link_public"
    )
    gis_link_technical = fields.Char(
        string="GIS Link (technical)", compute="_compute_gis_link_technical"
    )
    gis_link_minimal = fields.Char(
        string="GIS Link (minimal version)", compute="_compute_gis_link_minimal"
    )

    def _compute_gis_code(self):
        for record in self:
            record.gis_code = record.name or ""

    def _compute_gis_link_public(self):
        for record in self:
            # pylint: disable=protected-access
            record.gis_link_public = record._get_gis_link(public=True)

    def _compute_gis_link_technical(self):
        for record in self:
            # pylint: disable=protected-access
            record.gis_link_technical = record._get_gis_link(public=False)

    def _compute_gis_link_minimal(self):
        for record in self:
            # pylint: disable=protected-access
            record.gis_link_minimal = record._get_gis_link(minimal=True)

    def action_gis_viewer(self):
        company = self.env.company
        base_url = company.gis_viewer_url or self.DEFAULT_GIS_VIEWER
        codes = ",".join(rec.gis_code for rec in self if rec.gis_code)

        url = (
            f"{base_url}?arg={self._get_encrypted_credentials()}"
            f"&{self._param_gis_selection}={codes}"
        )

        xmin, ymin, xmax, ymax = self._get_bounding_box()
        if xmin < xmax and ymin < ymax and min(xmin, ymin, xmax, ymax) >= 0:
            url = f"{url}&bbox={xmin},{ymin},{xmax},{ymax}"

        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    @api.model
    def action_gis_viewer_global(self):
        company = self.env.company
        base_url = company.gis_viewer_url or self.DEFAULT_GIS_VIEWER
        url = f"{base_url}?arg={self._get_encrypted_credentials()}"
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def _get_cipher_key(self):
        company = self.env.company
        key = (company.gis_viewer_cipher_key or "").strip() or "z%C*F-JaNdRgUkXp"
        raw = key.encode("utf-8")

        if len(raw) in (16, 24, 32):
            return raw

        _logger.warning(
            "Invalid AES key length (%s) for company gis_viewer_cipher_key",
            len(raw),
        )
        return (raw + b"0" * 32)[:32]

    def _get_session_sid(self):
        try:
            return str(getattr(request.session, "sid", "") or "")
        except (AttributeError, RuntimeError):
            return ""

    def _get_encrypted_credentials(self):
        company = self.env.company
        username = company.gis_viewer_username
        password = company.gis_viewer_password
        if not (username and password):
            return ""

        plain = f"{username}-{password}-{self._get_session_sid()}".encode("utf-8")

        tz = pytz.timezone(self.DEFAULT_TZ)
        now_utc = pytz.utc.localize(datetime.datetime.utcnow())
        now_local = now_utc.astimezone(tz)

        minute = "00" if now_local.minute < 30 else "30"
        iv_str = now_local.strftime("%Y-%m-%dT%H:%M")
        iv = (iv_str[:14] + minute).encode("utf-8")

        cipher = AES.new(self._get_cipher_key(), AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(plain, AES.block_size))
        return base64.b64encode(encrypted).decode("utf-8")

    def _get_bounding_box(self):
        xmin = ymin = xmax = ymax = 0.0
        first = True
        mapped_field = self._gis_mapped_field

        for record in self:
            if mapped_field and not getattr(record, mapped_field, False):
                continue

            _srid, bbox = record.extract_bounding_box(
                record.geom_ewkt,
                force_square_shape=True,
            )
            bxmin, bymin, bxmax, bymax = bbox

            if first:
                first = False
                xmin, ymin, xmax, ymax = bxmin, bymin, bxmax, bymax
                continue

            xmin = min(xmin, bxmin)
            ymin = min(ymin, bymin)
            xmax = max(xmax, bxmax)
            ymax = max(ymax, bymax)

        return xmin, ymin, xmax, ymax

    def _get_gis_link(self, public=True, minimal=False):
        self.ensure_one()
        mapped_field = self._gis_mapped_field
        if mapped_field and not getattr(self, mapped_field, False):
            return ""

        company = self.env.company
        base_url = company.gis_viewer_url or self.DEFAULT_GIS_VIEWER
        additional_args = (
            company.gis_viewer_previs_additional_args or ""
        ).strip() or "mode=min"

        url = f"{base_url}?{self._param_gis_selection}={self.gis_code}"

        xmin, ymin, xmax, ymax = self._get_bounding_box()
        if xmin < xmax and ymin < ymax and min(xmin, ymin, xmax, ymax) >= 0:
            url = f"{url}&bbox={xmin},{ymin},{xmax},{ymax}"

        if minimal:
            return f"{url}&{additional_args}"
        if not public:
            return f"{url}&arg={self._get_encrypted_credentials()}"

        return url
