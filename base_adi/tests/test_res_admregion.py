# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase


class TestResAdmregion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Region = cls.env["res.admregion"]
        cls.Province = cls.env["res.province"]

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
            elif field.type in ("integer",):
                vals[name] = 1
            elif field.type in ("float", "monetary"):
                vals[name] = 1.0
            elif field.type in ("boolean",):
                vals[name] = True
            elif field.type in ("date",):
                vals[name] = "2026-01-01"
            elif field.type in ("datetime",):
                vals[name] = "2026-01-01 00:00:00"
            elif field.type in ("selection",):
                selection = field.selection(self.env) if callable(field.selection) else field.selection
                vals[name] = selection[0][0] if selection else False
            elif field.type == "many2one":
                comodel = self.env[field.comodel_name]
                # Use an existing record if possible; otherwise create a minimal one.
                record = comodel.search([], limit=1)
                if not record:
                    record = comodel.create(self._required_values_for(comodel))
                vals[name] = record.id
            else:
                # Skip unsupported required types (e.g. binary) unless caller provides it.
                pass

        vals.update(extra_vals)
        return vals

    def test_compute_number_of_provinces(self):
        region = self.Region.create({"alphanum_code": "North"})
        self.assertEqual(region.number_of_provinces, 0)

        p1 = self.Province.create(self._required_values_for(self.Province, {"region_id": region.id}))
        p2 = self.Province.create(self._required_values_for(self.Province, {"region_id": region.id}))
        self.assertTrue(p1 and p2)

        region.invalidate_recordset(["number_of_provinces"])
        self.assertEqual(region.number_of_provinces, 2)

    def test_action_show_provinces(self):
        region = self.Region.create({"alphanum_code": "South"})
        action = region.action_show_provinces()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.province")
        self.assertIn("view_mode", action)
        self.assertEqual(action["domain"], [("region_id", "=", region.id)])
        self.assertEqual(action["context"]["default_region_id"], region.id)
