# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import psycopg2
import requests
from odoo import api, fields, models
from odoo.tools import ormcache
from odoo.tools.lru import LRU
from PIL import Image, UnidentifiedImageError
from psycopg2 import sql
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)

BBox = List[float]
BBoxResult = Tuple[str, BBox]
BBoxFinalResult = Tuple[BBox, int, int]

_WMS_LRU = LRU(512)


class GisBaseModel(models.AbstractModel):
    """Base abstract model for GIS geometry integration.

    Provides shared infrastructure for linking Odoo models to PostGIS
    tables: EWKT/GeoJSON fields, WMS aerial image fetching with LRU
    cache, HTTP session management, and bounding-box utilities.

    Geometry-specific models (polygon.model, point.model, etc.) inherit
    this and override ``extract_bounding_box`` for their geometry type.
    """

    _name = "gis.base.model"
    _inherit = "gis.utils.mixin"
    _description = "GIS Base Model"

    NORMAL_SIZE = 512
    OGC_TIMEOUT = 20
    WITH_DECIMAL_COORDINATES = False

    _gis_table = ""
    _geom_field = "geom"
    _link_field = "name"
    _default_gis_srid = 25830

    geom_ewkt = fields.Char(
        string="EWKT Geometry",
        compute="_compute_geom_ewkt",
    )

    geom_geojson = fields.Char(
        string="GeoJSON Geometry",
        compute="_compute_geom_geojson",
    )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _make_wms_key(self, *parts):
        flat = "|".join(str(p) for p in parts)
        return self.sha1(flat)

    def _sql_ident(self, dotted_name: str) -> sql.SQL:
        parts = [p for p in (dotted_name or "").split(".") if p]
        if not parts:
            return sql.SQL("")
        return sql.SQL(".").join(sql.Identifier(p) for p in parts)

    @ormcache("self._gis_table", "self._geom_field", "self._link_field")
    def _geom_ok(self) -> bool:
        if not (self._gis_table and self._geom_field and self._link_field):
            return False
        try:
            with self.env.cr.savepoint():
                qry = sql.SQL("SELECT {link}, {geom} FROM {table} LIMIT 1").format(
                    link=sql.Identifier(self._link_field),
                    geom=sql.Identifier(self._geom_field),
                    table=self._sql_ident(self._gis_table),
                )
                self.env.cr.execute(qry)
            return True
        except (psycopg2.Error, ValueError):
            return False

    # ------------------------------------------------------------------
    # HTTP session & WMS download
    # ------------------------------------------------------------------

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
        try:
            resp = session.get(url, timeout=timeout, verify=verify_ssl)
        except requests.exceptions.Timeout as exc:
            _logger.warning(
                "WMS request timeout (timeout=%s): %s (%s)",
                timeout,
                url,
                exc,
            )
            return None
        except requests.exceptions.RequestException as exc:
            _logger.warning("WMS request error: %s (%s)", url, exc)
            return None

        if resp.status_code != 200:
            _logger.warning("WMS request failed (HTTP %s): %s", resp.status_code, url)
            return None

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "image/" not in ctype:
            _logger.warning(
                "WMS response is not an image (Content-Type: %s): %s", ctype, url
            )
            return None

        payload = resp.content
        if not payload:
            _logger.warning("WMS response has empty body: %s", url)
            return None

        try:
            img = Image.open(io.BytesIO(payload))
            img.verify()
        except (UnidentifiedImageError, OSError) as exc:
            _logger.warning("WMS response is not a valid image (%s): %s", exc, url)
            return None

        return payload

    # ------------------------------------------------------------------
    # Mapped-to-GIS helpers (used by child field computes)
    # ------------------------------------------------------------------

    def _compute_mapped_to_gis(self, field_name):
        """Set boolean *field_name* for each record (batched)."""
        geom_ok = self._geom_ok()
        names = [r.name for r in self if r.name] if geom_ok else []
        mapped_names = set()
        if names:
            qry = sql.SQL("SELECT {link} FROM {table} WHERE {link} = ANY(%s)").format(
                link=sql.Identifier(self._link_field),
                table=self._sql_ident(self._gis_table),
            )
            self.env.cr.execute(qry, (names,))
            mapped_names = {r[0] for r in self.env.cr.fetchall()}
        for record in self:
            record[field_name] = bool(record.name and record.name in mapped_names)

    def _search_mapped_to_gis(self, operator, value):
        """Search helper for mapped-to-GIS boolean fields."""
        record_ids = []
        is_mapped = (operator == "=" and value) or (operator == "!=" and not value)
        if not self._geom_ok():
            return [("id", "in", record_ids)]

        table = self._name.replace(".", "_")
        base = sql.SQL("SELECT t.id FROM {t} t ").format(
            t=sql.Identifier(table),
        )
        if is_mapped:
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

    # ------------------------------------------------------------------
    # GIS scalar query helper
    # ------------------------------------------------------------------

    def _gis_fetch_scalar(self, select_sql, field_name):
        """Fetch a single PostGIS scalar per record (batched).

        Args:
            select_sql (sql.SQL): SELECT expression using {geom}
                placeholder for the geometry column.
            field_name (str): Target field name on each record.
        """
        geom_ok = self._geom_ok()
        names = [r.name for r in self if r.name] if geom_ok else []
        results = {}
        if names:
            qry = sql.SQL(
                "SELECT {link}, {expr} FROM {table} WHERE {link} = ANY(%s)"
            ).format(
                link=sql.Identifier(self._link_field),
                expr=select_sql.format(
                    geom=sql.Identifier(self._geom_field),
                ),
                table=self._sql_ident(self._gis_table),
            )
            self.env.cr.execute(qry, (names,))
            results = dict(self.env.cr.fetchall())
        for record in self:
            record[field_name] = results.get(record.name) or ""

    def _invalidate_gis_geometry_fields(self):
        """Invalidate common computed GIS fields after table updates."""
        candidate_fields = [
            "geom_ewkt",
            "geom_geojson",
            "mapped_to_polygon",
            "mapped_to_point",
            "area_gis",
            "perimeter_gis",
            "centroid_ewkt",
            "oriented_envelope_ewkt",
            "bounding_box_str",
            "coord_x",
            "coord_y",
            "srid",
            "coord_str",
        ]
        fields_to_invalidate = [
            field_name for field_name in candidate_fields if field_name in self._fields
        ]
        if fields_to_invalidate:
            self.invalidate_recordset(fields_to_invalidate)

    def _ensure_ewkt_srid(self, ewkt, default_srid=None):
        """Ensure EWKT has SRID prefix for PostGIS."""
        value = (ewkt or "").strip()
        if not value:
            return ""
        if value.upper().startswith("SRID="):
            return value
        srid = int(default_srid or self._default_gis_srid)
        return "SRID=%s;%s" % (srid, value)

    def _gis_table_parts(self):
        """Return (schema, table) from ``_gis_table``."""
        parts = [part for part in (self._gis_table or "").split(".") if part]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        if len(parts) == 1:
            return "public", parts[0]
        return "public", ""

    def _get_target_geom_type(self):
        """Return geometry type declared in destination GIS column."""
        schema_name, table_name = (
            self._gis_table_parts()
        )  # pylint: disable=protected-access
        if not table_name:
            return ""
        self.env.cr.execute(
            """
            SELECT UPPER(postgis.postgis_typmod_type(a.atttypmod))
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            LIMIT 1
            """,
            (schema_name, table_name, self._geom_field),
        )
        row = self.env.cr.fetchone()
        geom_type = (row[0] or "") if row else ""
        return geom_type.upper()

    def _normalize_geom_expression_for_target(self, geom_expr, target_geom_type):
        """Build SQL expression that coerces ``geom_expr`` to target type."""
        target_type = (target_geom_type or "").upper()
        dim_by_type = {
            "POINT": 1,
            "MULTIPOINT": 1,
            "LINESTRING": 2,
            "MULTILINESTRING": 2,
            "POLYGON": 3,
            "MULTIPOLYGON": 3,
        }
        dim = dim_by_type.get(target_type)
        if not dim:
            return geom_expr
        if target_type.startswith("MULTI"):
            return (
                "postgis.ST_Multi("
                "postgis.ST_CollectionExtract(%s, %s)"
                ")" % (geom_expr, dim)
            )
        return (
            "postgis.ST_GeometryN("
            "postgis.ST_CollectionExtract(%s, %s), 1"
            ")" % (geom_expr, dim)
        )

    def _set_gis_geometry_from_ewkt(self, ewkt, default_srid=None):
        """Insert or replace geometry for current records in GIS table."""
        if not self._geom_ok():
            return False
        srid = int(default_srid or self._default_gis_srid)
        target_geom_type = (
            self._get_target_geom_type()
        )  # pylint: disable=protected-access
        normalized_geom_sql = self._normalize_geom_expression_for_target(  # pylint: disable=protected-access
            "postgis.ST_GeomFromEWKT(%s)::geometry",
            target_geom_type,
        )
        written = False
        for record in self:
            link_value = getattr(record, self._link_field, False)
            if not link_value:
                continue
            value = record._ensure_ewkt_srid(  # pylint: disable=protected-access
                ewkt,
                default_srid=srid,
            )
            if not value:
                continue
            self.env.cr.execute(
                sql.SQL("DELETE FROM {table} WHERE {link} = %s").format(
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                ),
                (link_value,),
            )
            self.env.cr.execute(
                sql.SQL(
                    "INSERT INTO {table} ({link}, {geom}) "
                    "VALUES (%s, " + normalized_geom_sql + ")"
                ).format(
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                    geom=sql.Identifier(self._geom_field),
                ),
                (link_value, value),
            )
            written = True
        if not written:
            return False
        self._invalidate_gis_geometry_fields()
        return True

    def _rename_gis_link(self, old_link, new_link):
        """Rename this record's GIS-table row from ``old_link`` to ``new_link``.

        Geometry lives in an external table keyed by ``_link_field`` (e.g. the
        record name). When that key changes (e.g. a parcel is re-coded) the GIS
        row must follow or the geometry link is lost. It is a no-op when the
        target key already exists, to avoid breaking the unique key.
        """
        if not self._geom_ok():
            return False
        if not old_link or not new_link or old_link == new_link:
            return False
        self.env.cr.execute(
            sql.SQL(
                "UPDATE {table} SET {link} = %s WHERE {link} = %s "
                "AND NOT EXISTS (SELECT 1 FROM {table} WHERE {link} = %s)"
            ).format(
                table=self._sql_ident(self._gis_table),
                link=sql.Identifier(self._link_field),
            ),
            (new_link, old_link, new_link),
        )
        self._invalidate_gis_geometry_fields()
        # The stored "mapped to GIS" flag may have been recomputed as False
        # while the GIS row still had the old key; force it to recompute now
        # that the row follows the new key.
        mapped_field = getattr(self, "_gis_mapped_field", "")
        if mapped_field and mapped_field in self._fields:
            field = self._fields[mapped_field]
            if field.compute:
                self.env.add_to_compute(field, self)
        return True

    def _set_gis_geometry_from_gml(
        self,
        gml_geometry,
        source_srid=None,
        target_srid=None,
    ):
        """Convert GML geometry to EWKT and persist it in GIS table."""
        source = int(source_srid or self._default_gis_srid)
        target = int(target_srid or self._default_gis_srid)
        target_geom_type = (
            self._get_target_geom_type()
        )  # pylint: disable=protected-access
        gml = (gml_geometry or "").strip()
        if not gml:
            return False
        base_geom_sql = "postgis.ST_SetSRID(postgis.ST_GeomFromGML(%s), %s)"
        if source == target:
            geom_sql = base_geom_sql
            params = (gml, source)
        else:
            geom_sql = "postgis.ST_Transform(%s, %%s)" % base_geom_sql
            params = (gml, source, target)

        normalized_geom_sql = self._normalize_geom_expression_for_target(  # pylint: disable=protected-access
            geom_sql,
            target_geom_type,
        )
        try:
            self.env.cr.execute(
                f"SELECT postgis.ST_AsEWKT({normalized_geom_sql})",
                params,
            )
            row = self.env.cr.fetchone()
        except psycopg2.Error as exc:
            raise ValueError(
                self.env._(
                    "Invalid GML geometry or unsupported spatial reference system."
                )
            ) from exc
        ewkt = row[0] if row else ""
        if not ewkt:
            return False
        return self._set_gis_geometry_from_ewkt(ewkt, default_srid=target)

    def _format_summary_names(self, names, max_names=8):
        if not names:
            return ""
        ordered_names = [str(name) for name in names if name]
        if len(ordered_names) <= max_names:
            return ", ".join(ordered_names)
        visible = ", ".join(ordered_names[:max_names])
        hidden = len(ordered_names) - max_names
        return self.env._(
            "%(visible)s (+%(hidden)s more)",
            visible=visible,
            hidden=hidden,
        )

    def _build_display_notification(
        self,
        title,
        lines,
        message_type,
        options=None,
    ):
        options = options or {}
        params = {
            "title": title,
            "message": "\n".join(lines),
            "type": message_type,
            "sticky": bool(options.get("sticky", False)),
        }
        if options.get("autoreload", False):
            params["next"] = {"type": "ir.actions.client", "tag": "reload"}

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def _build_result_message_action(self, title, lines, message_type):
        button_classes = {
            "success": "btn btn-primary",
            "warning": "btn btn-warning",
            "danger": "btn btn-danger",
        }
        button_class = button_classes.get(message_type, "btn btn-secondary")
        return {
            "type": "ir.actions.act_window.message",
            "title": title,
            "message": "\n".join(lines),
            "buttons": [
                {
                    "name": self.env._("Close and Reload"),
                    "type": "ir.actions.client",
                    "tag": "reload",
                    "classes": button_class,
                }
            ],
        }

    def _get_notification_type(self, has_errors, has_success):
        message_type = "success"
        if has_errors and has_success:
            message_type = "warning"
        elif has_errors and not has_success:
            message_type = "danger"
        return message_type

    def _split_records_by_gis_link(self):
        links = []
        by_link = {}
        without_link = []
        for record in self:
            link_value = getattr(record, self._link_field, False)
            if not link_value:
                without_link.append(record.display_name)
                continue
            links.append(link_value)
            by_link[link_value] = record
        return links, by_link, without_link

    def _fetch_existing_gis_links(self, links):
        if not links:
            return set()
        self.env.cr.execute(
            sql.SQL("SELECT {link} FROM {table} WHERE {link} = ANY(%s)").format(
                table=self._sql_ident(self._gis_table),
                link=sql.Identifier(self._link_field),
            ),
            (links,),
        )
        return {row[0] for row in self.env.cr.fetchall()}

    def _delete_existing_gis_links(self, existing_links):
        if not existing_links:
            return []
        errors = []
        try:
            self.env.cr.execute(
                sql.SQL("DELETE FROM {table} WHERE {link} = ANY(%s)").format(
                    table=self._sql_ident(self._gis_table),
                    link=sql.Identifier(self._link_field),
                ),
                (list(existing_links),),
            )
            self._invalidate_gis_geometry_fields()
        except psycopg2.Error as exc:
            errors.append(str(exc))
        return errors

    def _build_delete_gis_geometry_lines(
        self,
        deleted,
        without_geometry,
        without_link,
        errors,
    ):
        lines = [self.env._("Summary:")]
        lines.append(self.env._("- Deleted geometries: %(count)s", count=len(deleted)))
        lines.append(
            self.env._(
                "- Already without geometry: %(count)s",
                count=len(without_geometry),
            )
        )
        lines.append(
            self.env._(
                "- Without GIS identifier: %(count)s",
                count=len(without_link),
            )
        )
        lines.append(self.env._("- Errors: %(count)s", count=len(errors)))
        if deleted:
            lines.append(
                self.env._(
                    "Deleted geometry names: %(names)s",
                    names=self._format_summary_names(deleted),
                )
            )
        if without_geometry:
            lines.append(
                self.env._(
                    "Already without geometry names: %(names)s",
                    names=self._format_summary_names(without_geometry),
                )
            )
        if without_link:
            lines.append(
                self.env._(
                    "Without GIS identifier names: %(names)s",
                    names=self._format_summary_names(without_link),
                )
            )
        self._append_error_names_line(lines, errors)  # pylint: disable=protected-access
        return lines

    def _append_error_names_line(self, lines, errors):
        if not errors:
            return
        lines.append(
            self.env._(
                "Errors: %(names)s",
                names=self._format_summary_names(errors),
            )
        )

    def _delete_gis_geometry(self):
        """Delete geometry rows from GIS table for current records."""
        if not self._geom_ok():
            return
        link_values = [getattr(record, self._link_field, False) for record in self]
        link_values = [value for value in link_values if value]
        if not link_values:
            return
        self.env.cr.execute(
            sql.SQL("DELETE FROM {table} WHERE {link} = ANY(%s)").format(
                table=self._sql_ident(self._gis_table),
                link=sql.Identifier(self._link_field),
            ),
            (link_values,),
        )
        self._invalidate_gis_geometry_fields()

    def action_delete_gis_geometry(self):
        """Object action wrapper to remove GIS geometry for selected records."""
        deleted = []
        without_geometry = []
        without_link = []
        errors = []
        if not self._geom_ok():
            errors.append(self.env._("GIS table is not available for this model."))
        else:
            links, by_link, without_link = self._split_records_by_gis_link()
            existing_links = self._fetch_existing_gis_links(links)
            for link_value in links:
                record = by_link.get(link_value)
                if link_value in existing_links:
                    deleted.append(record.display_name)
                else:
                    without_geometry.append(record.display_name)
            errors.extend(self._delete_existing_gis_links(existing_links))
        lines = self._build_delete_gis_geometry_lines(
            deleted,
            without_geometry,
            without_link,
            errors,
        )
        message_type = self._get_notification_type(bool(errors), bool(deleted))
        return self._build_result_message_action(
            self.env._("GIS geometry deletion"),
            lines,
            message_type,
        )

    @api.depends("name")
    def _compute_geom_ewkt(self):
        self._gis_fetch_scalar(
            sql.SQL("postgis.st_asewkt({geom})"),
            "geom_ewkt",
        )

    @api.depends("name")
    def _compute_geom_geojson(self):
        self._gis_fetch_scalar(
            sql.SQL("postgis.st_asgeojson({geom})"),
            "geom_geojson",
        )

    # ------------------------------------------------------------------
    # Bounding box & coordinates
    # ------------------------------------------------------------------

    @api.model
    def extract_coordinates(self, geom_ewkt) -> Tuple[str, str]:
        """Extract SRID and WKT body from EWKT string.

        Returns:
            (srid, coordinates) - e.g. ("25830", "POLYGON((...))").
        """
        srid = ""
        coordinates = ""
        if geom_ewkt:
            pos = geom_ewkt.find(";")
            if pos != -1 and pos < len(geom_ewkt) - 1:
                coordinates = geom_ewkt[pos + 1 :]
                srid_part = geom_ewkt[:pos]
                eq_pos = srid_part.find("=")
                if eq_pos != -1 and eq_pos < len(srid_part) - 1:
                    srid = srid_part[eq_pos + 1 :]
                if not srid:
                    coordinates = ""
        return srid, coordinates

    @api.model
    # pylint: disable=unused-argument
    def extract_bounding_box(self, geom_ewkt, force_square_shape=True) -> BBoxResult:
        """Extract bounding box from EWKT geometry.

        Override in child models for geometry-specific parsing.
        Returns (srid, [minx, miny, maxx, maxy]) or (srid, []).
        """
        srid = self.extract_coordinates(geom_ewkt)[0]
        return srid, []

    @api.model
    def get_bbox_final(
        self,
        zoom,
        bbox_initial,
        image_width_initial,
        image_height_initial,
    ) -> BBoxFinalResult:
        """Apply zoom to bbox and compute pixel dimensions."""
        empty = ([0, 0, 0, 0], 0, 0)

        if not (
            bbox_initial
            and len(bbox_initial) == 4
            and image_width_initial >= 0
            and image_height_initial >= 0
        ):
            return empty

        if not (
            (bbox_initial[2] - bbox_initial[0]) > 0
            and (bbox_initial[3] - bbox_initial[1]) > 0
            and zoom >= 1
        ):
            return empty

        zoomed_bbox, width_m, height_m = self.apply_zoom_to_bbox(
            bbox_initial,
            zoom,
        )
        w_px, h_px = self.compute_pixel_dimensions(
            {
                "width_m": width_m,
                "height_m": height_m,
                "width_px_initial": image_width_initial,
                "height_px_initial": image_height_initial,
                "normal_size": self.NORMAL_SIZE,
            }
        )
        return list(zoomed_bbox), w_px, h_px

    # ------------------------------------------------------------------
    # WMS aerial images
    # ------------------------------------------------------------------

    def _prepare_wms_tasks(self, opts):
        """Prepare WMS tasks in main thread (ORM-safe).

        Returns list of (record_id, url, cache_key, cached|None).
        """
        tasks = []
        for rec in self:
            srid, bbox = rec.extract_bounding_box(
                rec.geom_ewkt,
                force_square_shape=opts["force_square_shape"],
            )
            if not (srid and bbox):
                continue
            bbox_final, w_px, h_px = rec.get_bbox_final(
                opts["zoom"],
                bbox,
                opts["image_width"],
                opts["image_height"],
            )
            if not (w_px > 0 and h_px > 0):
                continue
            url = self.build_wms_url(
                {
                    "link_field": rec._link_field,  # pylint: disable=protected-access
                    "rec_name": rec.name,
                    "srid": srid,
                    "bbox": bbox_final,
                    "w_px": w_px,
                    "h_px": h_px,
                    "opts": opts,
                }
            )
            key = self.sha1(url)
            tasks.append((rec.id, url, key, _WMS_LRU.get(key)))
        return tasks

    def _download_wms_images(self, pending, opts):
        """Download WMS images (threads do HTTP I/O only).

        Args:
            pending: list of (record_id, url, cache_key).
            opts: WMS options dict.
        Returns:
            dict {record_id: payload_bytes}.
        """
        downloaded = {}
        if not pending:
            return downloaded
        timeout = (10, self.OGC_TIMEOUT)
        verify_ssl = opts["verify_ssl"]
        session = self._build_session()
        try:
            if len(pending) == 1:
                rid, url, key = pending[0]
                payload = self._fetch_wms_bytes(
                    session,
                    url,
                    timeout=timeout,
                    verify_ssl=verify_ssl,
                )
                if payload:
                    _WMS_LRU[key] = payload
                    downloaded[rid] = payload
            else:
                self._download_parallel(
                    session,
                    pending,
                    {
                        "timeout": timeout,
                        "verify_ssl": verify_ssl,
                        "max_workers": opts["parallel_workers"],
                    },
                    downloaded,
                )
        finally:
            session.close()
        return downloaded

    def _download_parallel(self, session, pending, params, downloaded):
        """Download WMS images in parallel threads.

        Args:
            session: requests.Session.
            pending: list of (record_id, url, cache_key).
            params (dict): timeout, verify_ssl, max_workers.
            downloaded (dict): mutated with {rid: payload}.
        """
        workers = min(max(1, params["max_workers"]), len(pending))
        timeout = params["timeout"]
        verify_ssl = params["verify_ssl"]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(
                    self._fetch_wms_bytes,
                    session,
                    url,
                    timeout=timeout,
                    verify_ssl=verify_ssl,
                ): (rid, key)
                for rid, url, key in pending
            }
            for fut in as_completed(futures):
                rid, key = futures[fut]
                try:
                    payload = fut.result()
                except Exception as exc:  # noqa: BLE001  # pylint: disable=W0718
                    _logger.warning("WMS worker failed for record %s: %s", rid, exc)
                    continue
                if payload:
                    _WMS_LRU[key] = payload
                    downloaded[rid] = payload

    def get_aerial_image(self, **kwargs):
        """Fetch WMS aerial image(s).

        Kwargs: wms, layers, styles, image_width, image_height,
        image_format, zoom, get_raw, apply_filter,
        force_square_shape, verify_ssl, parallel_workers.
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

        tasks = self._prepare_wms_tasks(opts)

        results = {rec.id: None for rec in self}
        pending = []
        for rid, url, key, cached in tasks:
            if cached:
                results[rid] = cached
            else:
                pending.append((rid, url, key))

        downloaded = self._download_wms_images(pending, opts)
        results.update(downloaded)

        get_raw = opts["get_raw"]
        for rid, val in results.items():
            if val is not None:
                results[rid] = io.BytesIO(val) if get_raw else base64.b64encode(val)

        aerial_images = [results[rec.id] for rec in self]
        if all(img is None for img in aerial_images):
            return None
        if len(aerial_images) == 1:
            return aerial_images[0]
        return aerial_images
