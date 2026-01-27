# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestProductTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.ProductTemplate = cls.env["product.template"]
        cls.ProductCategory = cls.env["product.category"]

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.categ = cls.ProductCategory.create(
            {"name": "Test Categ", "category_code": 0}
        )

    def _create_template(self, **vals):
        data = {
            "name": "Test Product",
            "type": "service",
            "categ_id": self.categ.id,
            "uom_id": self.uom_unit.id,
            "uom_po_id": self.uom_unit.id,
        }
        data.update(vals)
        return self.ProductTemplate.create(data)

    def test_defaults(self):
        tmpl = self._create_template()
        self.assertEqual(tmpl.factor_quantity, 1.0)
        self.assertFalse(tmpl.link_with_billable_items)

    def test_factor_quantity_constraint_ok_zero(self):
        tmpl = self._create_template(factor_quantity=0.0)
        self.assertEqual(tmpl.factor_quantity, 0.0)

    def test_factor_quantity_constraint_fails_negative(self):
        tmpl = self._create_template()
        with self.assertRaises(
            Exception
        ):  # SQL constraint raises psycopg2 error wrapped by Odoo
            tmpl.write({"factor_quantity": -0.1})
