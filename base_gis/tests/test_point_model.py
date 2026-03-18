# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.base_gis.models.gis_base_model import GisBaseModel
from odoo.addons.base_gis.models.point_model import PointModel
from odoo.tests.common import TransactionCase


class DummyPointModel:
    """Minimal helper object to test pure geometry methods."""

    _default_buffer_m = 100.0

    @staticmethod
    def parse_point_coords(coords_str):
        return PointModel.parse_point_coords(coords_str)

    def extract_coordinates(self, geom_ewkt):
        return GisBaseModel.extract_coordinates(self, geom_ewkt)

    def extract_bounding_box(self, geom_ewkt):
        return PointModel.extract_bounding_box(self, geom_ewkt)


class TestPointModelParser(TransactionCase):

    def test_parse_point_coords(self):
        cases = [
            ("POINT(500000 4700000)", (500000.0, 4700000.0)),
            ("POINT (500000 4700000)", (500000.0, 4700000.0)),
            ("point(500000 4700000)", (500000.0, 4700000.0)),
            ("POINT(-3.5 40.1)", (-3.5, 40.1)),
            ("MULTIPOINT((10 20),(30 40))", None),
            ("LINESTRING(10 20,30 40)", None),
            ("POINT(abc def)", None),
            ("", None),
            (None, None),
        ]

        for coords, expected in cases:
            with self.subTest(coords=coords):
                result = PointModel.parse_point_coords(coords)
                self.assertEqual(result, expected)

    def test_parse_point_coords_rejects_invalid_shape(self):
        self.assertIsNone(PointModel.parse_point_coords("POINT(1 2 3)"))
        self.assertIsNone(PointModel.parse_point_coords("POINT()"))
        self.assertIsNone(PointModel.parse_point_coords("POLYGON((0 0,1 1,0 0))"))


class TestPointModelGeometry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.point = DummyPointModel()

    def test_extract_bounding_box(self):
        geom = "SRID=25830;POINT(500000 4700000)"

        srid, bbox = self.point.extract_bounding_box(geom)

        self.assertEqual(srid, "25830")
        self.assertEqual(
            bbox,
            [499900.0, 4699900.0, 500100.0, 4700100.0],
        )

    def test_extract_bounding_box_without_srid(self):
        geom = "POINT(10 20)"

        srid, bbox = self.point.extract_bounding_box(geom)

        self.assertEqual(srid, "")
        self.assertEqual(bbox, [])

    def test_extract_bounding_box_invalid_geometry(self):
        cases = [
            ("", ""),
            (None, ""),
            ("SRID=25830;LINESTRING(0 0,1 1)", "25830"),
            ("SRID=25830;MULTIPOINT((10 20),(30 40))", "25830"),
            ("SRID=25830;POINT(abc def)", "25830"),
        ]

        for geom, expected_srid in cases:
            with self.subTest(geom=geom):
                srid, bbox = self.point.extract_bounding_box(geom)
                self.assertEqual(srid, expected_srid)
                self.assertEqual(bbox, [])
