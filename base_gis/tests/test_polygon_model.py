# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from unittest.mock import patch

from odoo.tests.common import TransactionCase
from requests.exceptions import RequestException


class TestPolygonModel(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name

        super().setUpClass()
        cls.Poly = cls.env["base_gis.polygon_test"]

    def test_compute_fields_when_no_gis_config(self):
        rec = self.Poly.create({"name": "X"})
        self.assertFalse(rec.mapped_to_polygon)
        self.assertEqual(rec.geom_ewkt, "")
        self.assertEqual(rec.geom_geojson, "")
        self.assertEqual(rec.oriented_envelope_ewkt, "")
        self.assertEqual(rec.area_gis, 0)
        self.assertEqual(rec.perimeter_gis, 0)
        self.assertEqual(rec.centroid_ewkt, "")

    def test_extract_coordinates(self):
        srid, coords = self.Poly.extract_coordinates(
            "SRID=25830;POLYGON((0 0,1 0,1 1,0 0))"
        )
        self.assertEqual(srid, "25830")
        self.assertIn("polygon", coords.lower())

    def test_extract_bounding_box_polygon(self):
        srid, bbox = self.Poly.extract_bounding_box(
            "SRID=25830;POLYGON((0 0,10 0,10 5,0 0))", force_square_shape=False
        )
        self.assertEqual(srid, "25830")
        self.assertEqual(bbox, [0.0, 0.0, 10.0, 5.0])

    def test_get_bbox_final(self):
        bbox, w, h = self.Poly.get_bbox_final(
            zoom=2,
            bbox_initial=[0, 0, 10, 10],
            image_width_initial=0,
            image_height_initial=0,
        )
        self.assertEqual(bbox, [-5, -5, 15, 15])
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_search_mapped_to_polygon_when_no_gis_config(self):
        dom = self.Poly._search_mapped_to_polygon("=", True)
        self.assertEqual(dom, [("id", "in", [])])

    @patch("odoo.addons.base_gis.models.polygon_model.requests.get")
    def test_get_aerial_image_request_exception(self, mocked_get):
        mocked_get.side_effect = Exception(
            "boom"
        )  # will be treated as RequestException? not, but we don't want broad
        # Patch to raise a RequestException instead to follow contract

        mocked_get.side_effect = RequestException("boom")
        rec = self.Poly.create({"name": "X"})
        out = rec.get_aerial_image()
        self.assertIsNone(out)
