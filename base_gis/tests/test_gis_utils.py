# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import unittest

from odoo.addons.base_gis.models.gis_utils_mixin import GisUtilsMixin
from odoo.addons.base_gis.models.polygon_model import PolygonModel


class TestGisUtils(unittest.TestCase):
    """Tests for pure @staticmethod utilities in gis.utils.mixin."""

    # ------------------------------------------------------------------
    # sha1
    # ------------------------------------------------------------------

    def test_sha1_deterministic(self):
        self.assertEqual(
            GisUtilsMixin.sha1("hello"),
            GisUtilsMixin.sha1("hello"),
        )

    def test_sha1_different_inputs(self):
        self.assertNotEqual(
            GisUtilsMixin.sha1("a"),
            GisUtilsMixin.sha1("b"),
        )

    def test_sha1_hex_length(self):
        self.assertEqual(len(GisUtilsMixin.sha1("test")), 40)

    # ------------------------------------------------------------------
    # bounds_from_points
    # ------------------------------------------------------------------

    def test_bounds_from_points_empty(self):
        self.assertIsNone(GisUtilsMixin.bounds_from_points([]))

    def test_bounds_from_points_single(self):
        self.assertEqual(
            GisUtilsMixin.bounds_from_points([(5, 3)]),
            (5, 3, 5, 3),
        )

    def test_bounds_from_points_multiple(self):
        pts = [(0, 0), (10, 5), (3, 7)]
        self.assertEqual(
            GisUtilsMixin.bounds_from_points(pts),
            (0, 0, 10, 7),
        )

    # ------------------------------------------------------------------
    # force_square_bounds
    # ------------------------------------------------------------------

    def test_force_square_already_square(self):
        self.assertEqual(
            GisUtilsMixin.force_square_bounds(0, 0, 10, 10),
            (0, 0, 10, 10),
        )

    def test_force_square_wider(self):
        result = GisUtilsMixin.force_square_bounds(0, 0, 10, 4)
        width = result[2] - result[0]
        height = result[3] - result[1]
        self.assertEqual(width, height)

    def test_force_square_taller(self):
        result = GisUtilsMixin.force_square_bounds(0, 0, 4, 10)
        width = result[2] - result[0]
        height = result[3] - result[1]
        self.assertEqual(width, height)

    # ------------------------------------------------------------------
    # apply_zoom_to_bbox
    # ------------------------------------------------------------------

    def test_zoom_factor_one(self):
        bbox, width_m, height_m = GisUtilsMixin.apply_zoom_to_bbox(
            (0, 0, 10, 10),
            1,
        )
        self.assertEqual(bbox, (0, 0, 10, 10))
        self.assertEqual(width_m, 10)
        self.assertEqual(height_m, 10)

    def test_zoom_factor_two(self):
        bbox, width_m, height_m = GisUtilsMixin.apply_zoom_to_bbox(
            (0, 0, 10, 10),
            2,
        )
        self.assertEqual(bbox, (-5, -5, 15, 15))
        self.assertEqual(width_m, 20)
        self.assertEqual(height_m, 20)

    # ------------------------------------------------------------------
    # compute_pixel_dimensions
    # ------------------------------------------------------------------

    def test_pixel_dimensions_both_zero(self):
        w_px, h_px = GisUtilsMixin.compute_pixel_dimensions(
            {
                "width_m": 100,
                "height_m": 200,
                "width_px_initial": 0,
                "height_px_initial": 0,
                "normal_size": 512,
            }
        )
        self.assertEqual(h_px, 512)
        self.assertEqual(w_px, 256)

    def test_pixel_dimensions_width_zero(self):
        w_px, h_px = GisUtilsMixin.compute_pixel_dimensions(
            {
                "width_m": 100,
                "height_m": 200,
                "width_px_initial": 0,
                "height_px_initial": 512,
                "normal_size": 512,
            }
        )
        self.assertEqual(h_px, 512)
        self.assertEqual(w_px, 256)

    def test_pixel_dimensions_height_zero(self):
        w_px, h_px = GisUtilsMixin.compute_pixel_dimensions(
            {
                "width_m": 200,
                "height_m": 100,
                "width_px_initial": 512,
                "height_px_initial": 0,
                "normal_size": 512,
            }
        )
        self.assertEqual(w_px, 512)
        self.assertEqual(h_px, 256)

    def test_pixel_dimensions_both_set(self):
        w_px, h_px = GisUtilsMixin.compute_pixel_dimensions(
            {
                "width_m": 100,
                "height_m": 200,
                "width_px_initial": 300,
                "height_px_initial": 400,
                "normal_size": 512,
            }
        )
        self.assertEqual(w_px, 300)
        self.assertEqual(h_px, 400)

    # ------------------------------------------------------------------
    # build_wms_url
    # ------------------------------------------------------------------

    def test_build_wms_url_basic(self):
        url = GisUtilsMixin.build_wms_url(
            {
                "link_field": "name",
                "rec_name": "test",
                "srid": "25830",
                "bbox": (100, 200, 300, 400),
                "w_px": 512,
                "h_px": 512,
                "opts": {
                    "wms": "https://example.com/wms",
                    "layers": "layer1",
                    "styles": "default",
                    "apply_filter": False,
                    "image_format": "png",
                },
            }
        )
        self.assertIn("service=wms", url)
        self.assertIn("epsg:25830", url)
        self.assertIn("100,200,300,400", url)
        self.assertIn("width=512", url)
        self.assertNotIn("FILTER", url)

    def test_build_wms_url_with_filter(self):
        url = GisUtilsMixin.build_wms_url(
            {
                "link_field": "name",
                "rec_name": "PARCEL-001",
                "srid": "25830",
                "bbox": (100, 200, 300, 400),
                "w_px": 512,
                "h_px": 512,
                "opts": {
                    "wms": "https://example.com/wms",
                    "layers": "base,vector",
                    "styles": "default",
                    "apply_filter": True,
                    "image_format": "png",
                },
            }
        )
        self.assertIn("FILTER=", url)
        self.assertIn("PARCEL-001", url)


class TestPolygonUtils(unittest.TestCase):
    """Tests for pure @staticmethod utilities in polygon.model."""

    def test_parse_polygon_points_polygon(self):
        pts = PolygonModel.parse_polygon_points("POLYGON((0 0,10 0,10 5,0 5,0 0))")
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts[0], (0.0, 0.0))
        self.assertEqual(pts[2], (10.0, 5.0))

    def test_parse_polygon_points_multipolygon(self):
        pts = PolygonModel.parse_polygon_points(
            "MULTIPOLYGON(((0 0,10 0,10 5,0 5,0 0)))"
        )
        self.assertEqual(len(pts), 5)

    def test_parse_polygon_points_empty(self):
        self.assertEqual(PolygonModel.parse_polygon_points(""), [])

    def test_parse_polygon_points_invalid(self):
        self.assertEqual(
            PolygonModel.parse_polygon_points("invalid"),
            [],
        )
