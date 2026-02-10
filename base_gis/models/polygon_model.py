# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import hashlib
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import psycopg2
import requests
from odoo import api, fields, models
from odoo.tools.lru import LRU
from PIL import Image, UnidentifiedImageError
from psycopg2 import sql
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BBox = List[float]
BBoxResult = Tuple[str, BBox]
BBoxFinalResult = Tuple[BBox, int, int]

_WMS_LRU = LRU(512)


def _parse_polygon_points(coords_str):
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
                pass
    return pairs


def _bounds_from_points(points):
    """Return (minx, miny, maxx, maxy) from list of (x, y) pairs, or None if empty."""
    if not points:
        return None
    minx = maxx = points[0][0]
    miny = maxy = points[0][1]
    for x, y in points[1:]:
        minx = min(minx, x)
        maxx = max(maxx, x)
        miny = min(miny, y)
        maxy = max(maxy, y)
    return minx, miny, maxx, maxy


def _force_square_bounds(minx, miny, maxx, maxy):
    """Expand bbox to square (in place style), return (minx, miny, maxx, maxy)."""
    width = maxx - minx
    height = maxy - miny
    if width == height:
        return minx, miny, maxx, maxy
    if height > width:
        inc = round((height - width) / 2)
        return minx - inc, miny, maxx + inc, maxy
    inc = round((width - height) / 2)
    return minx, miny - inc, maxx, maxy + inc


def _apply_zoom_to_bbox(bbox_initial, zoom):
    """Return expanded bbox (minx, miny, maxx, maxy) and new meter dimensions."""
    minx, miny, maxx, maxy = bbox_initial
    width_m = maxx - minx
    height_m = maxy - miny
    new_width_m = width_m * zoom
    new_height_m = height_m * zoom
    offset_w = (new_width_m - width_m) / 2
    offset_h = (new_height_m - height_m) / 2
    new_minx = int(round(minx - offset_w))
    new_miny = int(round(miny - offset_h))
    new_maxx = int(round(maxx + offset_w))
    new_maxy = int(round(maxy + offset_h))
    return (
        (new_minx, new_miny, new_maxx, new_maxy),
        new_maxx - new_minx,
        new_maxy - new_miny,
    )


def _compute_pixel_dimensions(
    width_m, height_m, width_px_initial, height_px_initial, normal_size
):
    """Return (width_pixels, height_pixels) from meter dimensions and initial px."""
    w_px = width_px_initial
    h_px = height_px_initial
    if width_px_initial == 0 and height_px_initial == 0:
        h_px = normal_size
    if w_px == 0 or h_px == 0:
        if w_px == 0:
            w_px = int(round((width_m * h_px) / height_m))
        else:
            h_px = int(round((height_m * w_px) / width_m))
    return w_px, h_px


def _build_wms_url(rec, srid, bbox_final, w_px, h_px, opts):
    """Build WMS GetMap URL for one record."""
    minx, miny, maxx, maxy = bbox_final
    cql_filter = ""
    if opts.get("apply_filter"):
        n_layers = max(0, len(opts.get("layers", "").split(",")) - 1)
        cql_filter = (
            "&FILTER="
            + "()" * n_layers
            + '(<Filter><PropertyIsLike wildCard="*" singleChar="." escape="!">'
            + f"<PropertyName>{rec._link_field}</PropertyName>"
            + f"<Literal>{rec.name}</Literal>"
            + "</PropertyIsLike></Filter>)"
        )
    return (
        f"{opts.get('wms', '')}?service=wms"
        f"&version=1.3.0&request=getmap&crs=epsg:{srid}"
        f"&bbox={minx},{miny},{maxx},{maxy}"
        f"&width={w_px}&height={h_px}"
        f"&layers={opts.get('layers', '')}&styles={opts.get('styles', 'default')}"
        f"&transparent=true{cql_filter}"
        f"&format=image/{opts.get('image_format', 'png')}"
    )


class PolygonModel(models.AbstractModel):
    _name = "polygon.model"
    _description = "Polygon Model"

    NORMAL_SIZE = 512
    OGC_TIMEOUT = 5
    WITH_DECIMAL_COORDINATES = False

    _gis_table = ""
    _geom_field = "geom"
    _link_field = "name"

    mapped_to_polygon = fields.Boolean(
        string="Mapped to polygon",
        compute="_compute_mapped_to_polygon",
        search="_search_mapped_to_polygon",
        store=True,
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

    def _sha1(self, s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def _make_wms_key(self, *parts) -> str:
        flat = "|".join(str(p) for p in parts)
        return self._sha1(flat)

    def _sql_ident(self, dotted_name: str) -> sql.SQL:
        parts = [p for p in (dotted_name or "").split(".") if p]
        if not parts:
            return sql.SQL("")
        return sql.SQL(".").join(sql.Identifier(p) for p in parts)

    def _geom_ok(self) -> bool:
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
            self.env.cr.rollback()
            return False

    def _build_session(self):
        sess = requests.Session()
        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.25,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=20,
            pool_maxsize=20,
        )
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        sess.headers.update(
            {
                "User-Agent": "Odoo WMS client",
                "Accept": "image/*,*/*;q=0.8",
            }
        )
        return sess

    def _fetch_wms_bytes(self, session, url: str, *, timeout, verify_ssl: bool):
        resp = session.get(url, timeout=timeout, verify=verify_ssl)
        if resp.status_code != 200:
            return None

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "image/" not in ctype:
            return None

        payload = resp.content
        if not payload:
            return None

        try:
            img = Image.open(io.BytesIO(payload))
            img.verify()
        except (UnidentifiedImageError, OSError):
            return None

        return payload

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
        points = _parse_polygon_points(coordinates)
        bounds = _bounds_from_points(points)
        if not bounds:
            return srid, bounding_box
        minx, miny, maxx, maxy = bounds
        if force_square_shape:
            minx, miny, maxx, maxy = _force_square_bounds(minx, miny, maxx, maxy)
        return srid, [minx, miny, maxx, maxy]

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
        width_m = maxx - minx
        height_m = maxy - miny
        if not (width_m > 0 and height_m > 0 and zoom >= 1):
            return bbox_final, image_width_final, image_height_final

        (minx, miny, maxx, maxy), width_m, height_m = _apply_zoom_to_bbox(
            bbox_initial, zoom
        )
        w_px, h_px = _compute_pixel_dimensions(
            width_m,
            height_m,
            image_width_initial,
            image_height_initial,
            self.NORMAL_SIZE,
        )
        return [minx, miny, maxx, maxy], w_px, h_px

    def get_aerial_image(self, **kwargs):
        """Fetch WMS aerial image(s). Kwargs: wms, layers, styles, image_width,
        image_height, image_format, zoom, get_raw, apply_filter, force_square_shape,
        verify_ssl, parallel_workers.
        """
        defaults = {
            "wms": "https://www.ign.es/wms-inspire/pnoa-ma",
            "layers": "OI.OrthoimageCoverage",
            "styles": "default",
            "image_width": 0,
            "image_height": 512,
            "image_format": "png",
            "zoom": 1.2,
            "get_raw": False,
            "apply_filter": False,
            "force_square_shape": True,
            "verify_ssl": True,
            "parallel_workers": 6,
        }
        opts = {k: kwargs.get(k, v) for k, v in defaults.items()}

        def _task(rec):
            srid, bbox = rec.extract_bounding_box(
                rec.geom_ewkt, force_square_shape=opts["force_square_shape"]
            )
            if not (srid and bbox):
                return rec.id, None
            bbox_final, w_px, h_px = rec.get_bbox_final(
                opts["zoom"], bbox, opts["image_width"], opts["image_height"]
            )
            if not (w_px > 0 and h_px > 0):
                return rec.id, None
            url = _build_wms_url(rec, srid, bbox_final, w_px, h_px, opts)
            key = self._sha1(url)
            cached = _WMS_LRU.get(key)
            if cached:
                return rec.id, cached
            session = self._build_session()
            try:
                payload = self._fetch_wms_bytes(
                    session,
                    url,
                    timeout=(2, getattr(rec, "OGC_TIMEOUT", 10)),
                    verify_ssl=opts["verify_ssl"],
                )
            finally:
                session.close()
            if payload:
                _WMS_LRU[key] = payload
            return rec.id, payload

        results = {rec.id: None for rec in self}
        if len(self) == 1:
            rid, payload = _task(self[0])
            if payload:
                results[rid] = (
                    io.BytesIO(payload)
                    if opts["get_raw"]
                    else base64.b64encode(payload)
                )
        else:
            workers = min(max(1, opts["parallel_workers"]), len(self))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(_task, rec) for rec in self]
                for fut in as_completed(futures):
                    rid, payload = fut.result()
                    if payload:
                        results[rid] = (
                            io.BytesIO(payload)
                            if opts["get_raw"]
                            else base64.b64encode(payload)
                        )
        aerial_images = [results[rec.id] for rec in self]
        if all(i is None for i in aerial_images):
            return None
        if len(aerial_images) == 1:
            return aerial_images[0]
        return aerial_images
