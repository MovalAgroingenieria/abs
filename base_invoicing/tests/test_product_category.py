# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestProductCategory(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Category = cls.env["product.category"]
        cls.IrModel = cls.env["ir.model"]

    def test_constraint_category_code_unique(self):
        c1 = self.Category.create({"name": "C1", "category_code": 10})
        self.assertTrue(c1)

        with self.assertRaises(ValidationError):
            self.Category.create({"name": "C2", "category_code": 10})

    def test_copy_resets_category_code(self):
        c1 = self.Category.create({"name": "C1", "category_code": 7})
        c2 = c1.copy()
        self.assertEqual(c2.category_code, 0)

    def test_unlink_blocked_for_coded(self):
        c1 = self.Category.create({"name": "C1", "category_code": 3})
        with self.assertRaises(UserError):
            c1.unlink()

    def test_sanitize_vals_when_model_unset(self):
        IrModelFields = self.env["ir.model.fields"]
        billable_model = self.IrModel.search(
            [("model", "=", "base_invoicing.billable_item_test")], limit=1
        )
        qty_field = IrModelFields.search(
            [
                ("model_id", "=", billable_model.id),
                ("name", "=", "quantity"),
                ("ttype", "=", "float"),
            ],
            limit=1,
        )
        group_field = IrModelFields.search(
            [
                ("model_id", "=", billable_model.id),
                ("name", "=", "id"),
                ("ttype", "=", "integer"),
            ],
            limit=1,
        )
        c1 = self.Category.create(
            {
                "name": "C1",
                "billable_item_model_id": billable_model.id,
                "billable_item_quantity_field_id": qty_field.id,
                "billable_item_group_field_id": group_field.id,
                "aux_field_ids": [
                    (0, 0, {"field_id": qty_field.id}),
                ],
            }
        )
        self.assertTrue(c1.billable_item_model_id)
        self.assertTrue(c1.billable_item_group_field_id)
        self.assertEqual(len(c1.aux_field_ids), 1)

        c1.write({"billable_item_model_id": False})
        self.assertFalse(c1.billable_item_quantity_field_id)
        self.assertFalse(c1.billable_item_group_field_id)
        self.assertEqual(len(c1.aux_field_ids), 0)

    def test_display_name_short_context(self):
        c1 = self.Category.create({"name": "C1", "category_code": 2})
        c1_ctx = c1.with_context(short_name_categories=True)
        c1_ctx.invalidate_recordset(["display_name"])
        self.assertIn("(cat. #2)", c1_ctx.display_name)

    def test_display_name_default_context(self):
        standard = self.Category.search([("category_code", "=", 1)], limit=1)
        self.assertTrue(standard, "Missing standard category with code 1 in data")
        standard.invalidate_recordset(["display_name"])
        self.assertIn("standard", standard.display_name.lower())
