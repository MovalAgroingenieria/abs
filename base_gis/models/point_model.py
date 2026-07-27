# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re

from odoo import api, fields, models
from psycopg2 import sql


class PointModel(models.AbstractModel):
    """Point GIS model.
    Extends ``gis.base.model`` with point-specific fields.
    """

    _name = "point.model"
    _description = "Point Model"
    _inherit = "gis.base.model"

    WITH_DECIMAL_COORDINATES = True

    _default_buffer_m = 100.0

    # ------------------------------------------------------------------
    # Pure geometry helpers (no ORM needed)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_point_coords(coords_str):
        """Parse WKT POINT coordinates into (x, y) float tuple.

        Accepts: POINT(x y), POINT (x y), point(x y)
        Rejects: MULTIPOINT (by design).
        Returns: (x, y) or None.
        """

        if not coords_str:
            return None

        coords = coords_str.strip()

        # Reject multipoint
        if re.match(r"^\s*multipoint\s*\(", coords, re.IGNORECASE):
            return None

        match = re.match(
            r"^\s*point\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)",
            coords,
            re.IGNORECASE,
        )

        if not match:
            return None

        try:
            x = float(match.group(1))
            y = float(match.group(2))
        except (ValueError, TypeError):
            return None

        return (x, y)

    mapped_to_point = fields.Boolean(
        string="Mapped to point",
        compute="_compute_mapped_to_point",
        search="_search_mapped_to_point",
        store=True,
    )

    coord_x = fields.Float(
        string="X Coordinate",
        compute="_compute_point_data",
    )

    coord_y = fields.Float(
        string="Y Coordinate",
        compute="_compute_point_data",
    )

    srid = fields.Char(
        string="SRID",
        compute="_compute_point_data",
    )

    coord_str = fields.Char(
        string="Coordinates formatted",
        compute="_compute_coord_str",
    )

    # ------------------------------------------------------------------
    # Mapped-to-point
    # ------------------------------------------------------------------

    @api.depends("name")
    def _compute_mapped_to_point(self):
        self._compute_mapped_to_gis("mapped_to_point")

    def _search_mapped_to_point(self, operator, value):
        return self._search_mapped_to_gis(operator, value)

    # ------------------------------------------------------------------
    # Point-specific computes
    # ------------------------------------------------------------------

    @api.depends("geom_ewkt")
    def _compute_point_data(self):
        geom_ok = self._geom_ok()

        for record in self:
            record.coord_x = False
            record.coord_y = False
            record.srid = False

        if not geom_ok:
            return

        names = [r.name for r in self if r.name]
        if not names:
            return

        qry = sql.SQL("""
            SELECT g.{link},
                postgis.st_x(g.{geom}),
                postgis.st_y(g.{geom}),
                postgis.st_srid(g.{geom})
            FROM {table} g
            JOIN unnest(%s) AS t(name)
                ON g.{link} = t.name
            """).format(
            link=sql.Identifier(self._link_field),
            geom=sql.Identifier(self._geom_field),
            table=self._sql_ident(self._gis_table),
        )
        self.env.cr.execute(qry, (names,))

        point_data = {name: (x, y, srid) for name, x, y, srid in self.env.cr.fetchall()}

        for record in self:
            data = point_data.get(record.name)
            if not data:
                continue

            x, y, srid = data
            record.coord_x = x
            record.coord_y = y
            record.srid = f"EPSG:{srid}" if srid else False

    @api.depends("coord_x", "coord_y", "srid")
    def _compute_coord_str(self):
        precision = "%.6f" if self.WITH_DECIMAL_COORDINATES else "%.0f"

        lang = self.env.user.lang or "en_US"
        lang_model = self.env["res.lang"].search([("code", "=", lang)], limit=1)

        for record in self:
            record.coord_str = ""

            if not record.coord_x or not record.coord_y or not record.srid:
                continue

            if not lang_model:
                continue

            x = lang_model.format(precision, record.coord_x, True)
            y = lang_model.format(precision, record.coord_y, True)

            record.coord_str = f"{record.srid} ({x}, {y})"

    # ------------------------------------------------------------------
    # Point bounding-box extraction (overrides base)
    # ------------------------------------------------------------------

    @api.model  # pylint: disable=unused-argument
    def extract_bounding_box(self, geom_ewkt, force_square_shape=False):
        """Return bounding box around a point geometry.

        For points the bbox is generated using a symmetric buffer
        around the coordinate.
        """

        _ = force_square_shape

        srid, coordinates = self.extract_coordinates(geom_ewkt)

        if not coordinates:
            return srid, []

        point = self.parse_point_coords(coordinates)
        if point is None:
            return srid, []

        x, y = point
        buf = self._default_buffer_m

        xmin = x - buf
        ymin = y - buf
        xmax = x + buf
        ymax = y + buf

        return srid, [xmin, ymin, xmax, ymax]
