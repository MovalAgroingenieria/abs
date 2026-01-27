# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .tool import _required_values_for


class TestResMunicipality(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Region = cls.env["res.admregion"]
        cls.Province = cls.env["res.province"]
        cls.Municipality = cls.env["res.municipality"]
        cls.Place = cls.env["res.place"]

    def _create_region_province(self):
        region = self.Region.create({"alphanum_code": "R1"})
        province = self.Province.create(
            _required_values_for(self, self.Province, {"region_id": region.id})
        )
        return region, province

    def test_related_region_id(self):
        region, province = self._create_region_province()
        municipality = self.Municipality.create(
            {"alphanum_code": "M1", "province_id": province.id}
        )
        self.assertEqual(municipality.region_id, region)

    def test_compute_number_of_places(self):
        _region, province = self._create_region_province()
        municipality = self.Municipality.create(
            {"alphanum_code": "M2", "province_id": province.id}
        )
        self.assertEqual(municipality.number_of_places, 0)

        p1 = self.Place.create(
            _required_values_for(self, self.Place, {"municipality_id": municipality.id})
        )
        p2 = self.Place.create(
            _required_values_for(self, self.Place, {"municipality_id": municipality.id})
        )
        self.assertTrue(p1 and p2)

        municipality.invalidate_recordset(["number_of_places"])
        self.assertEqual(municipality.number_of_places, 2)

    def test_constraint_duplicate_in_province(self):
        _region, province = self._create_region_province()
        self.Municipality.create({"alphanum_code": "Dup", "province_id": province.id})

        with self.assertRaises(ValidationError):
            self.Municipality.create(
                {"alphanum_code": "Dup", "province_id": province.id}
            )

    def test_action_show_places(self):
        _region, province = self._create_region_province()
        municipality = self.Municipality.create(
            {"alphanum_code": "M4", "province_id": province.id}
        )
        action = municipality.action_show_places()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.place")
        self.assertEqual(action["domain"], [("municipality_id", "=", municipality.id)])
        self.assertEqual(action["context"]["default_municipality_id"], municipality.id)
