# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.base_gis.models.gis_base_model import GisBaseModel
from odoo.addons.base_gis.models.polygon_model import PolygonModel
from odoo.tests.common import TransactionCase


class DummyPolygonModel:
    """Minimal helper object to test pure geometry methods."""

    NORMAL_SIZE = 512
    OGC_TIMEOUT = 5
    WITH_DECIMAL_COORDINATES = False

    @staticmethod
    def parse_polygon_points(coords_str):
        return PolygonModel.parse_polygon_points(coords_str)

    def extract_coordinates(self, geom_ewkt):
        return GisBaseModel.extract_coordinates(self, geom_ewkt)

    def extract_bounding_box(self, geom_ewkt, force_square_shape=True):
        return PolygonModel.extract_bounding_box(
            self,
            geom_ewkt,
            force_square_shape=force_square_shape,
        )

    def get_bbox_final(
        self,
        zoom,
        bbox_initial,
        image_width_initial=0,
        image_height_initial=0,
    ):
        return GisBaseModel.get_bbox_final(
            self,
            zoom=zoom,
            bbox_initial=bbox_initial,
            image_width_initial=image_width_initial,
            image_height_initial=image_height_initial,
        )

    def compute_pixel_dimensions(
        self,
        width_m,
        height_m,
        image_width_initial=0,
        image_height_initial=0,
        normal_size=512,
    ):
        if image_width_initial and image_height_initial:
            return image_width_initial, image_height_initial

        width_m = max(float(width_m), 1.0)
        height_m = max(float(height_m), 1.0)

        if width_m >= height_m:
            width_px = normal_size
            height_px = max(int(round(normal_size * height_m / width_m)), 1)
        else:
            height_px = normal_size
            width_px = max(int(round(normal_size * width_m / height_m)), 1)

        return width_px, height_px

    @staticmethod
    def bounds_from_points(points):
        if not points:
            return []

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]

        return [min(xs), min(ys), max(xs), max(ys)]

    @staticmethod
    def force_square_bounds(minx, miny, maxx, maxy):
        width = maxx - minx
        height = maxy - miny

        if width == height:
            return minx, miny, maxx, maxy

        center_x = (minx + maxx) / 2.0
        center_y = (miny + maxy) / 2.0
        half_size = max(width, height) / 2.0

        return (
            center_x - half_size,
            center_y - half_size,
            center_x + half_size,
            center_y + half_size,
        )

    @staticmethod
    def apply_zoom_to_bbox(bbox, zoom):
        minx, miny, maxx, maxy = bbox
        width = maxx - minx
        height = maxy - miny

        factor = float(zoom)
        grow_x = width * (factor - 1.0) / 2.0
        grow_y = height * (factor - 1.0) / 2.0

        return (
            [minx - grow_x, miny - grow_y, maxx + grow_x, maxy + grow_y],
            width * factor,
            height * factor,
        )

    @staticmethod
    def ensure_non_zero_image_size(width, height):
        return max(int(width), 1), max(int(height), 1)


class TestPolygonModelParser(TransactionCase):

    def test_parse_polygon_points_polygon(self):
        coords = "POLYGON((0 0,1 0,1 1,0 0))"

        result = PolygonModel.parse_polygon_points(coords)

        self.assertEqual(
            result,
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)],
        )

    def test_parse_polygon_points_multipolygon(self):
        coords = "MULTIPOLYGON(((0 0,2 0,2 2,0 0)))"

        result = PolygonModel.parse_polygon_points(coords)

        self.assertEqual(
            result,
            [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 0.0)],
        )

    def test_parse_polygon_points_invalid_or_empty(self):
        cases = [
            "",
            None,
            "POINT(1 2)",
            "LINESTRING(0 0,1 1)",
            "POLYGON(())",
        ]

        for coords in cases:
            with self.subTest(coords=coords):
                self.assertEqual(PolygonModel.parse_polygon_points(coords), [])

    def test_parse_polygon_points_skips_invalid_pairs(self):
        coords = "POLYGON((0 0,1 x,2 2,0 0))"

        result = PolygonModel.parse_polygon_points(coords)

        self.assertEqual(result, [(0.0, 0.0), (2.0, 2.0), (0.0, 0.0)])


class TestPolygonModelGeometry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.polygon = DummyPolygonModel()

    def test_extract_coordinates(self):
        srid, coords = self.polygon.extract_coordinates(
            "SRID=25830;POLYGON((0 0,1 0,1 1,0 0))"
        )
        self.assertEqual(srid, "25830")
        self.assertIn("polygon", coords.lower())

    def test_extract_bounding_box_polygon(self):
        srid, bbox = self.polygon.extract_bounding_box(
            "SRID=25830;POLYGON((0 0,10 0,10 5,0 0))",
            force_square_shape=False,
        )

        self.assertEqual(srid, "25830")
        self.assertEqual(bbox, [0.0, 0.0, 10.0, 5.0])

    def test_extract_bounding_box_polygon_force_square(self):
        srid, bbox = self.polygon.extract_bounding_box(
            "SRID=25830;POLYGON((0 0,10 0,10 5,0 0))",
            force_square_shape=True,
        )

        self.assertEqual(srid, "25830")
        self.assertEqual(bbox, [0.0, -2.5, 10.0, 7.5])

    def test_extract_bounding_box_multipolygon(self):
        srid, bbox = self.polygon.extract_bounding_box(
            "SRID=25830;MULTIPOLYGON(((0 0,10 0,10 5,0 0)))",
            force_square_shape=False,
        )

        self.assertEqual(srid, "25830")
        self.assertEqual(bbox, [0.0, 0.0, 10.0, 5.0])

    def test_extract_bounding_box_invalid_geometry(self):
        cases = [
            ("", ""),
            (None, ""),
            ("SRID=25830;POINT(1 2)", "25830"),
            ("SRID=25830;LINESTRING(0 0,1 1)", "25830"),
            ("SRID=25830;POLYGON(())", "25830"),
        ]

        for geom, expected_srid in cases:
            with self.subTest(geom=geom):
                srid, bbox = self.polygon.extract_bounding_box(
                    geom,
                    force_square_shape=False,
                )
                self.assertEqual(srid, expected_srid)
                self.assertEqual(bbox, [])

    def test_get_bbox_final(self):
        bbox, width, height = self.polygon.get_bbox_final(
            zoom=2,
            bbox_initial=[0, 0, 10, 10],
            image_width_initial=0,
            image_height_initial=0,
        )

        self.assertEqual(bbox, [-5.0, -5.0, 15.0, 15.0])
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
