# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase


class TestProductCategory(TransactionCase):
    def test_update_vals_resets_fields_when_model_is_unset(self):
        categ = self.env["product.category"].create({"name": "Test", "category_code": 0})
        categ.write(
            {
                "billable_item_model_id": False,
                "billable_item_quantity_field": "qty",
                "billable_item_group_field": "grp",
                "billable_item_domain": "[('id','!=',0)]",
                "aux_01_char_field": "foo",
            }
        )
        categ.write({"billable_item_model_id": False})
        self.assertFalse(categ.billable_item_quantity_field)
        self.assertFalse(categ.billable_item_group_field)
        self.assertFalse(categ.billable_item_domain)
        self.assertFalse(categ.aux_01_char_field)

    def test_copy_resets_category_code(self):
        categ = self.env["product.category"].create({"name": "Test", "category_code": 5})
        copied = categ.copy()
        self.assertEqual(copied.category_code, 0)
