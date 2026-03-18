# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import hashlib

from odoo import models


class GisUtilsMixin(models.AbstractModel):
    """Pure-utility mixin for GIS geometry operations.

    Contains only static/class-level helpers that do NOT require
    ORM access (no ``self.env``, no cursor, no fields).  Any model
    that inherits this mixin gains bbox, zoom, pixel-dimension and
    WMS-URL helpers through normal MRO.

    Inherited by ``gis.base.model``; concrete geometry models
    (``polygon.model``, ``point.model``, …) get these automatically.
    """

    _name = "gis.utils.mixin"
    _description = "GIS Utilities Mixin"

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def sha1(text):
        """Return SHA-1 hex digest of *text*."""
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Bounding-box helpers
    # ------------------------------------------------------------------

    @staticmethod
    def bounds_from_points(points):
        """Return (minx, miny, maxx, maxy) from (x, y) pairs, or None."""
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

    @staticmethod
    def force_square_bounds(minx, miny, maxx, maxy):
        """Expand bbox to square, return (minx, miny, maxx, maxy)."""
        width = maxx - minx
        height = maxy - miny
        if width == height:
            return minx, miny, maxx, maxy
        if height > width:
            inc = round((height - width) / 2)
            return minx - inc, miny, maxx + inc, maxy
        inc = round((width - height) / 2)
        return minx, miny - inc, maxx, maxy + inc

    @staticmethod
    def apply_zoom_to_bbox(bbox_initial, zoom):
        """Return expanded bbox and new meter dimensions."""
        minx, miny, maxx, maxy = bbox_initial
        offset_w = ((maxx - minx) * zoom - (maxx - minx)) / 2
        offset_h = ((maxy - miny) * zoom - (maxy - miny)) / 2
        new_bbox = (
            int(round(minx - offset_w)),
            int(round(miny - offset_h)),
            int(round(maxx + offset_w)),
            int(round(maxy + offset_h)),
        )
        return (
            new_bbox,
            new_bbox[2] - new_bbox[0],
            new_bbox[3] - new_bbox[1],
        )

    @staticmethod
    def compute_pixel_dimensions(params):
        """Return (width_pixels, height_pixels) from meter dimensions.

        Args:
            params (dict): Dictionary with keys:
                - width_m: width in meters
                - height_m: height in meters
                - width_px_initial: initial pixel width (0 = auto)
                - height_px_initial: initial pixel height (0 = auto)
                - normal_size: default pixel size
        """
        width_m = params["width_m"]
        height_m = params["height_m"]
        w_px = params.get("width_px_initial", 0)
        h_px = params.get("height_px_initial", 0)
        normal_size = params.get("normal_size", 512)
        if w_px == 0 and h_px == 0:
            h_px = normal_size
        if w_px == 0 or h_px == 0:
            if w_px == 0:
                w_px = int(round((width_m * h_px) / height_m))
            else:
                h_px = int(round((height_m * w_px) / width_m))
        return w_px, h_px

    # ------------------------------------------------------------------
    # WMS URL builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_wms_url(params):
        """Build WMS GetMap URL.
        Args:
            params (dict): Dictionary with keys:
                - link_field: field name for CQL filter
                - rec_name: record name for CQL filter
                - srid: EPSG code
                - bbox: (minx, miny, maxx, maxy)
                - w_px, h_px: pixel dimensions
                - opts: WMS options dict
        """
        minx, miny, maxx, maxy = params["bbox"]
        opts = params["opts"]
        cql_filter = ""
        if opts.get("apply_filter"):
            n_layers = max(0, len(opts.get("layers", "").split(",")) - 1)
            cql_filter = (
                "&FILTER="
                + "()" * n_layers
                + '<(<Filter><PropertyIsLike wildCard="*"'
                + ' singleChar="." escape="!">'
                + "<PropertyName>"
                + f"{params['link_field']}"
                + "</PropertyName>"
                + f"<Literal>{params['rec_name']}</Literal>"
                + "</PropertyIsLike></Filter>)"
            )
        return (
            f"{opts.get('wms', '')}?service=wms"
            f"&version=1.3.0&request=getmap"
            f"&crs=epsg:{params['srid']}"
            f"&bbox={minx},{miny},{maxx},{maxy}"
            f"&width={params['w_px']}&height={params['h_px']}"
            f"&layers={opts.get('layers', '')}"
            f"&styles={opts.get('styles', 'default')}"
            f"&transparent=true{cql_filter}"
            f"&format=image/{opts.get('image_format', 'png')}"
        )
