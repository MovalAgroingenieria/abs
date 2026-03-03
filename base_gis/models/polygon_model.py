# 2024-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re

from odoo import api, fields, models
from psycopg2 import sql


class PolygonModel(models.AbstractModel):
    """Polygon/MultiPolygon GIS model.

    Extends ``gis.base.model`` with polygon-specific fields (area,
    perimeter, centroid, oriented envelope) and bounding-box extraction.
    """

    _name = "polygon.model"
    _description = "Polygon Model"
    _inherit = "gis.base.model"

    # ------------------------------------------------------------------
    # Pure geometry helpers (no ORM needed)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_polygon_points(coords_str):
        """Parse WKT coordinates string into list of (x, y) float pairs."""
        if not coords_str:
            return []
        coords = coords_str.lower()
        points_str = ""
        if "multipolygon" in coords:
            match = re.search(r"\(\(\((.*?)\)\)\)", coords)
            points_str = match.group(1) if match else ""
        elif "polygon" in coords:
            match = re.search(r"\(\((.*?)\)\)", coords)
            points_str = match.group(1) if match else ""
        if not points_str:
            return []
        points_str = (
            points_str.replace("),(", ", ").replace("), (", ", ").replace(", ", ",")
        )
        pairs = []
        for part in points_str.split(","):
            xy = part.split(" ")
            if len(xy) == 2:
                try:
                    pairs.append((float(xy[0]), float(xy[1])))
                except (ValueError, TypeError):
                    continue
        return pairs

    mapped_to_polygon = fields.Boolean(
        string="Mapped to polygon",
        compute="_compute_mapped_to_polygon",
        search="_search_mapped_to_polygon",
        store=True,
    )

    oriented_envelope_ewkt = fields.Char(
        string="EWKT Geometry for oriented envelope",
        compute="_compute_oriented_envelope_ewkt",
    )

    area_gis = fields.Integer(
        string="GIS Area (m²)",
        compute="_compute_area_gis",
    )

    perimeter_gis = fields.Integer(
        string="GIS Perimeter (m)",
        compute="_compute_perimeter_gis",
    )

    centroid_ewkt = fields.Char(
        string="EWKT Centroid",
        compute="_compute_centroid_ewkt",
    )

    bounding_box_str = fields.Char(
        string="Bounding box as string",
        compute="_compute_bounding_box_str",
    )

    # ------------------------------------------------------------------
    # Mapped-to-polygon
    # ------------------------------------------------------------------

    @api.depends("name")
    def _compute_mapped_to_polygon(self):
        self._compute_mapped_to_gis("mapped_to_polygon")

    def _search_mapped_to_polygon(self, operator, value):
        return self._search_mapped_to_gis(operator, value)

    # ------------------------------------------------------------------
    # Polygon-specific computes
    # ------------------------------------------------------------------

    @api.depends("name")
    def _compute_oriented_envelope_ewkt(self):
        self._gis_fetch_scalar(
            sql.SQL("postgis.st_asewkt(postgis.st_orientedenvelope({geom}))"),
            "oriented_envelope_ewkt",
        )

    def _gis_fetch_polygon_metric(self, metric_sql, field_name):
        """Fetch a PostGIS polygon metric per record (batched).

        Args:
            metric_sql (sql.SQL): PostGIS expression with {geom}.
            field_name (str): Target field name on each record.
        """
        geom_ok = self._geom_ok()
        names = [r.name for r in self if r.name] if geom_ok else []
        metric_map = {}
        if names:
            qry = sql.SQL(
                "SELECT {link}, postgis.geometrytype({geom}),"
                + " {metric} FROM {table} WHERE {link} = ANY(%s)"
            ).format(
                link=sql.Identifier(self._link_field),
                geom=sql.Identifier(self._geom_field),
                metric=metric_sql.format(
                    geom=sql.Identifier(self._geom_field),
                ),
                table=self._sql_ident(self._gis_table),
            )
            self.env.cr.execute(qry, (names,))
            for name, geom_type, val in self.env.cr.fetchall():
                gt = (geom_type or "").lower()
                if gt in ("polygon", "multipolygon"):
                    if val is not None:
                        metric_map[name] = round(float(val))
        for record in self:
            record[field_name] = metric_map.get(record.name, 0)

    @api.depends("name")
    def _compute_area_gis(self):
        self._gis_fetch_polygon_metric(
            sql.SQL("postgis.st_area({geom})"),
            "area_gis",
        )

    @api.depends("name")
    def _compute_perimeter_gis(self):
        self._gis_fetch_polygon_metric(
            sql.SQL("postgis.st_perimeter({geom})"),
            "perimeter_gis",
        )

    @api.depends("name")
    def _compute_centroid_ewkt(self):
        self._gis_fetch_scalar(
            sql.SQL("postgis.st_asewkt(postgis.st_centroid({geom}))"),
            "centroid_ewkt",
        )

    @api.depends("geom_ewkt")
    def _compute_bounding_box_str(self):
        lang = self.env.user.lang or "en_US"
        lang_model = self.env["res.lang"].search(
            [("code", "=", lang)],
            limit=1,
        )
        precision = "%.6f" if self.WITH_DECIMAL_COORDINATES else "%.0f"
        for record in self:
            result = ""
            if record.geom_ewkt:
                srid, bbox = record.extract_bounding_box(
                    record.geom_ewkt,
                    force_square_shape=False,
                )
                if srid and bbox and len(bbox) == 4 and lang_model:
                    vals = [lang_model.format(precision, v, True) for v in bbox]
                    result = (
                        f"EPSG:{srid} ({vals[0]}, {vals[1]})"
                        f" - ({vals[2]}, {vals[3]})"
                    )
            record.bounding_box_str = result

    # ------------------------------------------------------------------
    # Polygon bounding-box extraction (overrides base)
    # ------------------------------------------------------------------

    @api.model
    def extract_bounding_box(
        self,
        geom_ewkt,
        force_square_shape=True,
    ):
        """Extract bounding box from POLYGON/MULTIPOLYGON EWKT."""
        bounding_box = []
        srid, coordinates = self.extract_coordinates(geom_ewkt)
        if not coordinates:
            return srid, bounding_box
        points = self.parse_polygon_points(coordinates)
        bounds = self.bounds_from_points(points)
        if not bounds:
            return srid, bounding_box
        minx, miny, maxx, maxy = bounds
        if force_square_shape:
            minx, miny, maxx, maxy = self.force_square_bounds(
                minx,
                miny,
                maxx,
                maxy,
            )
        return srid, [minx, miny, maxx, maxy]
