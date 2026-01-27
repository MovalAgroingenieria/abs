# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase

from .tool import _required_values_for


class TestResProvince(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Region = cls.env["res.admregion"]
        cls.Province = cls.env["res.province"]
        cls.Municipality = cls.env["res.municipality"]

    def test_compute_number_of_municipalities(self):
        region = self.Region.create({"alphanum_code": "R1"})
        province = self.Province.create(
            _required_values_for(self, self.Province, {"region_id": region.id})
        )
        self.assertEqual(province.number_of_municipalities, 0)

        m1 = self.Municipality.create(
            {"alphanum_code": "M1", "province_id": province.id}
        )
        m2 = self.Municipality.create(
            {"alphanum_code": "M2", "province_id": province.id}
        )
        self.assertTrue(m1 and m2)

        province.invalidate_recordset(["number_of_municipalities"])
        self.assertEqual(province.number_of_municipalities, 2)

    def test_action_show_municipalities(self):
        region = self.Region.create({"alphanum_code": "R2"})
        province = self.Province.create(
            _required_values_for(self, self.Province, {"region_id": region.id})
        )

        action = province.action_show_municipalities()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.municipality")
        self.assertEqual(action["domain"], [("province_id", "=", province.id)])
        self.assertEqual(action["context"]["default_province_id"], province.id)
