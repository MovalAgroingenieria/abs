# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountSelectableItem(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Selectable = cls.env["account.selectable.item"]
        cls.Productlink = cls.env["account.invoiceset.productlink"]
        cls.Category = cls.env["product.category"]
        cls.Invoiceset = cls.env["account.invoiceset"]

        cls.partner = cls.env["res.partner"].create({"name": "P1"})

        cls.categ = cls.Category.create(
            {
                "name": "Cat GIS",
                "aux_desc": "Name={{ billable_item.name }}|ID={{ billable_item.id }}",
            }
        )

        tmpl = cls.env["product.template"].create(
            {
                "name": "Prod T",
                "type": "service",
                "categ_id": cls.categ.id,
            }
        )
        cls.product = tmpl.product_variant_id

        cls.invoiceset = cls.Invoiceset.create(
            {
                "alphanum_code": "SET-T1",
                "description": "Test",
                "invoice_date": "2026-01-27",
                "invoice_user_id": cls.env.user.id,
            }
        )
        cls.productlink = cls.Productlink.create(
            {
                "invoiceset_id": cls.invoiceset.id,
                "product_id": cls.product.id,
            }
        )

    def _create_item(self, **vals):
        base = {
            "productlink_id": self.productlink.id,
            "billable_item_model": "res.partner",
            "billable_item_res_id": self.partner.id,
            "partner_id": self.partner.id,
            "quantity": 1.0,
            "selected": True,
        }
        base.update(vals)
        return self.Selectable.create(base)

    def test_selected_message(self):
        item = self._create_item(selected=True)
        self.assertEqual(item.selected_message, self.env._("Selected"))

        item.write({"selected": False})
        item.invalidate_recordset(["selected_message"])
        self.assertEqual(item.selected_message, self.env._("Excluded"))

    def test_rendered_aux_desc_ok_and_pipe_to_newline(self):
        item = self._create_item()
        self.assertIn("Name=", item.rendered_aux_desc)
        self.assertIn("\n", item.rendered_aux_desc)

    def test_rendered_aux_desc_empty_when_missing_ref(self):
        item = self._create_item(billable_item_model=False)
        self.assertEqual(item.rendered_aux_desc, "")

    def test_action_select_deselect_updates_productlink_populated(self):
        item = self._create_item(selected=True)
        self.productlink.invalidate_recordset(["populated"])
        self.assertTrue(self.productlink.populated)

        item.action_deselect_items()
        self.productlink.invalidate_recordset(["populated"])
        self.assertFalse(self.productlink.populated)

        item.action_select_items()
        self.productlink.invalidate_recordset(["populated"])
        self.assertTrue(self.productlink.populated)

    def test_template_error_is_handled(self):
        # Invalid Jinja2 syntax is rejected on save with ValidationError
        with self.assertRaises(ValidationError) as cm:
            self.categ.write({"aux_desc": "{{ billable_item.name "})
        self.assertIn("Template for selection lines", str(cm.exception))
