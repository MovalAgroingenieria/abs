# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase


class TestResProvince(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Region = cls.env["res.admregion"]
        cls.Province = cls.env["res.province"]
        cls.Municipality = cls.env["res.municipality"]

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

    def test_compute_number_of_municipalities(self):
        region = self.Region.create({"alphanum_code": "R1"})
        province = self.Province.create(self._required_values_for(self.Province, {"region_id": region.id}))
        self.assertEqual(province.number_of_municipalities, 0)

        m1 = self.Municipality.create({"alphanum_code": "M1", "province_id": province.id})
        m2 = self.Municipality.create({"alphanum_code": "M2", "province_id": province.id})
        self.assertTrue(m1 and m2)

        province.invalidate_recordset(["number_of_municipalities"])
        self.assertEqual(province.number_of_municipalities, 2)

    def test_action_show_municipalities(self):
        region = self.Region.create({"alphanum_code": "R2"})
        province = self.Province.create(self._required_values_for(self.Province, {"region_id": region.id}))

        action = province.action_show_municipalities()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.municipality")
        self.assertEqual(action["domain"], [("province_id", "=", province.id)])
        self.assertEqual(action["context"]["default_province_id"], province.id)
