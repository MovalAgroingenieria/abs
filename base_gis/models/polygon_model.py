# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-locals
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import base64
import io
import re
from typing import List, Tuple

import psycopg2
import requests
from odoo import api, fields, models
from PIL import Image, UnidentifiedImageError
from psycopg2 import sql
from requests.exceptions import RequestException

BBox = List[float]
BBoxResult = Tuple[str, BBox]
BBoxFinalResult = Tuple[BBox, int, int]


class PolygonModel(models.AbstractModel):
    _name = "polygon.model"
    _description = "Polygon Model"

    # Default size for WMS images.
    NORMAL_SIZE = 512

    # Timeout for getmap requests.
    OGC_TIMEOUT = 5

    # Decimals for coordinates.
    WITH_DECIMAL_COORDINATES = False

    # Linked GIS table ("wua_gis_parcel", for example).
    _gis_table = ""

    # "geom" field.
    _geom_field = "geom"

    # Field for link.
    _link_field = "name"

    mapped_to_polygon = fields.Boolean(
        string="Mapped to polygon",
        compute="_compute_mapped_to_polygon",
        search="_search_mapped_to_polygon",
    )

    geom_ewkt = fields.Char(
        string="EWKT Geometry",
        compute="_compute_geom_ewkt",
    )

    geom_geojson = fields.Char(
        string="GeoJSON Geometry",
        compute="_compute_geom_geojson",
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

    # ------------------------------ SQL helpers ------------------------------

    def _sql_ident(self, dotted_name: str) -> sql.SQL:
        """Return a safe SQL identifier for dotted names (schema.table)."""
        parts = [p for p in (dotted_name or "").split(".") if p]
        if not parts:
            # caller must handle empty config
            return sql.SQL("")
        return sql.SQL(".").join(sql.Identifier(p) for p in parts)

    def _geom_ok(self) -> bool:
        """Check if GIS config points to an existing table/fields."""
        if not (self._gis_table and self._geom_field and self._link_field):
            return False

        try:
            qry = sql.SQL("SELECT {link}, {geom} FROM {table} LIMIT 1").format(
                link=sql.Identifier(self._link_field),
                geom=sql.Identifier(self._geom_field),
                table=self._sql_ident(self._gis_table),
            )
            self.env.cr.execute(qry)
            return True
        except (psycopg2.Error, ValueError):
            # Ensure we do not keep a broken transaction
            self.env.cr.rollback()
            return False

    # ------------------------------ compute fields ------------------------------

    @api.depends("name")
    def _compute_mapped_to_polygon(self):
        geom_ok = self._geom_ok()
        for record in self:
            mapped = False
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT {link} FROM {table} WHERE {link} = %s LIMIT 1"
                ).format(
                    link=sql.Identifier(self._link_field),
                    table=self._sql_ident(self._gis_table),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                mapped = bool(row)
            record.mapped_to_polygon = mapped

    def _search_mapped_to_polygon(self, operator, value):
        record_ids = []
        mapped_to_polygon = (operator == "=" and value) or (
            operator == "!=" and not value
        )

        if not self._geom_ok():
            return [("id", "in", record_ids)]

        table = self._name.replace(".", "_")
        base = sql.SQL("SELECT t.id FROM {t} t ").format(t=sql.Identifier(table))

        if mapped_to_polygon:
            qry = base + sql.SQL("INNER JOIN {gt} gt ON t.name = gt.{link}").format(
                gt=self._sql_ident(self._gis_table),
                link=sql.Identifier(self._link_field),
            )
        else:
            qry = base + sql.SQL(
                "LEFT JOIN {gt} gt ON t.name = gt.{link} WHERE gt.gid IS NULL"
            ).format(
                gt=self._sql_ident(self._gis_table),
                link=sql.Identifier(self._link_field),
            )

        self.env.cr.execute(qry)
        record_ids = [r[0] for r in self.env.cr.fetchall() or []]
        return [("id", "in", record_ids)]

    @api.depends("name")
    def _compute_geom_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            val = ""
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.st_asewkt({geom}) FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                val = row[0] if row and row[0] else ""
            record.geom_ewkt = val

    @api.depends("name")
    def _compute_geom_geojson(self):
        geom_ok = self._geom_ok()
        for record in self:
            val = ""
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.st_asgeojson({geom}) FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                val = row[0] if row and row[0] else ""
            record.geom_geojson = val

    @api.depends("name")
    def _compute_oriented_envelope_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            val = ""
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.st_asewkt(postgis.st_orientedenvelope({geom})) "
                    "FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                val = row[0] if row and row[0] else ""
            record.oriented_envelope_ewkt = val

    @api.depends("name")
    def _compute_area_gis(self):
        geom_ok = self._geom_ok()
        for record in self:
            area_val = 0
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.geometrytype({geom}), postgis.st_area({geom}) "
                    "FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                if row and row[0]:
                    geom_type = (row[0] or "").lower()
                    if geom_type in ("polygon", "multipolygon") and row[1] is not None:
                        area_val = round(float(row[1]))
            record.area_gis = area_val

    @api.depends("name")
    def _compute_perimeter_gis(self):
        geom_ok = self._geom_ok()
        for record in self:
            per_val = 0
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.geometrytype({geom}), postgis.st_perimeter({geom}) "
                    "FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                if row and row[0]:
                    geom_type = (row[0] or "").lower()
                    if geom_type in ("polygon", "multipolygon") and row[1] is not None:
                        per_val = round(float(row[1]))
            record.perimeter_gis = per_val

    @api.depends("name")
    def _compute_centroid_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            val = ""
            if geom_ok and record.name:
                qry = sql.SQL(
                    "SELECT postgis.st_asewkt(st_centroid({geom})) "
                    "FROM {table} WHERE {link} = %s"
                ).format(
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                )
                self.env.cr.execute(qry, (record.name,))
                row = self.env.cr.fetchone()
                val = row[0] if row and row[0] else ""
            record.centroid_ewkt = val

    @api.depends("geom_ewkt")
    def _compute_bounding_box_str(self):
        lang = self.env.user.lang or "en_US"
        lang_model = self.env["res.lang"].search([("code", "=", lang)], limit=1)
        precision = "%.6f" if self.WITH_DECIMAL_COORDINATES else "%.0f"

        for record in self:
            bounding_box_str = ""
            if record.geom_ewkt:
                srid, bounding_box = record.extract_bounding_box(
                    record.geom_ewkt, force_square_shape=False
                )
                if srid and bounding_box and len(bounding_box) == 4 and lang_model:
                    minx = lang_model.format(precision, bounding_box[0], True)
                    miny = lang_model.format(precision, bounding_box[1], True)
                    maxx = lang_model.format(precision, bounding_box[2], True)
                    maxy = lang_model.format(precision, bounding_box[3], True)
                    bounding_box_str = (
                        f"EPSG:{srid} ({minx}, {miny}) - ({maxx}, {maxy})"
                    )
            record.bounding_box_str = bounding_box_str

    # ------------------------------ geometry helpers ------------------------------

    @api.model
    def extract_coordinates(self, geom_ewkt) -> Tuple[str, str]:
        srid = ""
        coordinates = ""
        if geom_ewkt:
            pos_semicolon = geom_ewkt.find(";")
            if pos_semicolon != -1 and pos_semicolon < len(geom_ewkt) - 1:
                coordinates = geom_ewkt[pos_semicolon + 1 :]
                srid_temp = geom_ewkt[0:pos_semicolon]
                pos_equal = srid_temp.find("=")
                if pos_equal != -1 and pos_equal < len(srid_temp) - 1:
                    srid = srid_temp[pos_equal + 1 :]
                if not srid:
                    coordinates = ""
        return srid, coordinates

    @api.model
    def extract_bounding_box(self, geom_ewkt, force_square_shape=True) -> BBoxResult:
        bounding_box: BBox = []
        srid, coordinates = self.extract_coordinates(geom_ewkt)
        if not coordinates:
            return srid, bounding_box

        coords = coordinates.lower()
        points = ""
        if "multipolygon" in coords:
            match = re.search(r"\(\(\((.*?)\)\)\)", coords)
            points = match.group(1) if match else ""
        elif "polygon" in coords:
            match = re.search(r"\(\((.*?)\)\)", coords)
            points = match.group(1) if match else ""

        if not points:
            return srid, bounding_box

        points = points.replace("),(", ", ").replace("), (", ", ")
        points = points.replace(", ", ",")
        list_of_points = points.split(",")

        first_point = True
        minx = maxx = miny = maxy = 0.0

        for point in list_of_points:
            xy = point.split(" ")
            if len(xy) != 2:
                continue
            x = float(xy[0])
            y = float(xy[1])
            if first_point:
                first_point = False
                minx = maxx = x
                miny = maxy = y
                continue
            minx = min(minx, x)
            maxx = max(maxx, x)
            miny = min(miny, y)
            maxy = max(maxy, y)

        if first_point:
            return srid, bounding_box

        if force_square_shape:
            w = maxx - minx
            h = maxy - miny
            if w != h:
                if h > w:
                    inc = round((h - w) / 2)
                    minx -= inc
                    maxx += inc
                else:
                    inc = round((w - h) / 2)
                    miny -= inc
                    maxy += inc

        bounding_box = [minx, miny, maxx, maxy]
        return srid, bounding_box

    @api.model
    def get_bbox_final(
        self, zoom, bbox_initial, image_width_initial, image_height_initial
    ) -> BBoxFinalResult:
        bbox_final = [0, 0, 0, 0]
        image_width_final = 0
        image_height_final = 0

        if not (
            bbox_initial
            and len(bbox_initial) == 4
            and image_width_initial >= 0
            and image_height_initial >= 0
        ):
            return bbox_final, image_width_final, image_height_final

        minx, miny, maxx, maxy = bbox_initial
        image_width_meters = maxx - minx
        image_height_meters = maxy - miny
        if not (image_width_meters > 0 and image_height_meters > 0 and zoom >= 1):
            return bbox_final, image_width_final, image_height_final

        new_image_width_meters = image_width_meters * zoom
        new_image_height_meters = image_height_meters * zoom
        dif_width_meters = new_image_width_meters - image_width_meters
        dif_height_meters = new_image_height_meters - image_height_meters

        offset_width_meters = dif_width_meters / 2
        offset_height_meters = dif_height_meters / 2

        minx = int(round(minx - offset_width_meters))
        miny = int(round(miny - offset_height_meters))
        maxx = int(round(maxx + offset_width_meters))
        maxy = int(round(maxy + offset_height_meters))

        if image_width_initial == 0 and image_height_initial == 0:
            image_height_initial = self.NORMAL_SIZE

        image_width_meters = maxx - minx
        image_height_meters = maxy - miny

        image_height_pixels = image_height_initial
        image_width_pixels = image_width_initial
        if image_width_pixels == 0 or image_height_pixels == 0:
            if image_width_pixels == 0:
                image_width_pixels = int(
                    round(
                        (image_width_meters * image_height_pixels) / image_height_meters
                    )
                )
            else:
                image_height_pixels = int(
                    round(
                        (image_height_meters * image_width_pixels) / image_width_meters
                    )
                )

        bbox_final = [minx, miny, maxx, maxy]
        return bbox_final, image_width_pixels, image_height_pixels

    # ------------------------------ WMS fetch ------------------------------

    def get_aerial_image(
        self,
        wms="https://www.ign.es/wms-inspire/pnoa-ma",
        layers="OI.OrthoimageCoverage",
        styles="default",
        image_width=0,
        image_height=512,
        image_format="png",
        zoom=1.2,
        get_raw=False,
        apply_filter=False,
        force_square_shape=True,
        verify_ssl=True,
    ):
        aerial_images = []

        number_of_layers = max(0, len(layers.split(",")) - 1)

        for record in self:
            image = None
            srid, bbox = record.extract_bounding_box(
                record.geom_ewkt, force_square_shape=force_square_shape
            )
            if not (srid and bbox):
                aerial_images.append(None)
                continue

            bbox_final, w_px, h_px = self.get_bbox_final(
                zoom, bbox, image_width, image_height
            )
            if not (w_px > 0 and h_px > 0):
                aerial_images.append(None)
                continue

            minx, miny, maxx, maxy = bbox_final
            cql_filter = ""
            if apply_filter:
                cql_filter = (
                    "&FILTER="
                    + "()" * number_of_layers
                    + '(<Filter><PropertyIsLike wildCard="*" singleChar="." escape="!">'
                    + f"<PropertyName>{self._link_field}</PropertyName>"
                    + f"<Literal>{record.name}</Literal>"
                    + "</PropertyIsLike></Filter>)"
                )

            url = (
                f"{wms}?service=wms"
                f"&version=1.3.0&request=getmap&crs=epsg:{srid}"
                f"&bbox={minx},{miny},{maxx},{maxy}"
                f"&width={w_px}&height={h_px}"
                f"&layers={layers}&styles={styles}"
                f"&transparent=true{cql_filter}"
                f"&format=image/{image_format}"
            )

            try:
                resp = requests.get(
                    url, stream=True, timeout=self.OGC_TIMEOUT, verify=verify_ssl
                )
                resp.raise_for_status()
            except RequestException:
                aerial_images.append(None)
                continue

            raw = io.BytesIO(resp.content)
            try:
                Image.open(raw)
            except (UnidentifiedImageError, OSError):
                aerial_images.append(None)
                continue

            if get_raw:
                image = raw
            else:
                image = base64.b64encode(raw.getvalue()).decode("ascii")

            aerial_images.append(image)

        if all(i is None for i in aerial_images):
            return None
        if len(aerial_images) == 1:
            return aerial_images[0]
        return aerial_images
