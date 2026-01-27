# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestResMunicipality(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Region = cls.env["res.admregion"]
        cls.Province = cls.env["res.province"]
        cls.Municipality = cls.env["res.municipality"]
        cls.Place = cls.env["res.place"]

    def _required_values_for(self, model, extra_vals=None):
        extra_vals = dict(extra_vals or {})
        vals = {}

        for name, field in model._fields.items():
            if not field.required:
                continue
            if field.compute or field.related:
                continue
            if name in extra_vals:
                continue
            if name in ("id", "create_uid", "create_date", "write_uid", "write_date", "display_name"):
                continue

            if field.type in ("char", "text", "html"):
                vals[name] = "x"
            elif field.type == "integer":
                vals[name] = 1
            elif field.type in ("float", "monetary"):
                vals[name] = 1.0
            elif field.type == "boolean":
                vals[name] = True
            elif field.type == "date":
                vals[name] = "2026-01-01"
            elif field.type == "datetime":
                vals[name] = "2026-01-01 00:00:00"
            elif field.type == "selection":
                selection = field.selection(self.env) if callable(field.selection) else field.selection
                vals[name] = selection[0][0] if selection else False
            elif field.type == "many2one":
                comodel = self.env[field.comodel_name]
                record = comodel.search([], limit=1)
                if not record:
                    record = comodel.create(self._required_values_for(comodel))
                vals[name] = record.id

        vals.update(extra_vals)
        return vals

    def _create_region_province(self):
        region = self.Region.create({"alphanum_code": "R1"})
        province = self.Province.create(self._required_values_for(self.Province, {"region_id": region.id}))
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

        p1 = self.Place.create(self._required_values_for(self.Place, {"municipality_id": municipality.id}))
        p2 = self.Place.create(self._required_values_for(self.Place, {"municipality_id": municipality.id}))
        self.assertTrue(p1 and p2)

        municipality.invalidate_recordset(["number_of_places"])
        self.assertEqual(municipality.number_of_places, 2)

    def test_constraint_duplicate_in_province(self):
        _region, province = self._create_region_province()
        self.Municipality.create({"alphanum_code": "Dup", "province_id": province.id})

        with self.assertRaises(ValidationError):
            self.Municipality.create({"alphanum_code": "Dup", "province_id": province.id})

    def test_name_get_with_context(self):
        _region, province = self._create_region_province()
        municipality = self.Municipality.create(
            {"alphanum_code": "M3", "province_id": province.id}
        )

        name_default = dict(municipality.name_get()).get(municipality.id)
        self.assertEqual(name_default, "M3")

        municipality_ctx = municipality.with_context(municipality_with_province=True)
        name_ctx = dict(municipality_ctx.name_get()).get(municipality.id)
        self.assertIn("M3", name_ctx)
        self.assertIn(province.alphanum_code, name_ctx)

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
