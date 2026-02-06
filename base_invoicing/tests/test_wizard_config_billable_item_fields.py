# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestWizardConfigBillableItemFields(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()

        cls.Category = cls.env["product.category"]
        cls.ProductTemplate = cls.env["product.template"]
        cls.Invoiceset = cls.env["account.invoiceset"]
        cls.Productlink = cls.env["account.invoiceset.productlink"]
        cls.Wizard = cls.env["wizard.config.billable.item.fields"]

        cls.categ = cls.Category.create(
            {
                "name": "Cat Test",
                "category_code": 10,
                "aux_desc": "X",
            }
        )
        tmpl = cls.ProductTemplate.create(
            {
                "name": "Prod Test",
                "type": "service",
                "categ_id": cls.categ.id,
            }
        )
        cls.product = tmpl.product_variant_id

        cls.invoiceset = cls.Invoiceset.create(
            {
                "alphanum_code": "SET-WZ",
                "description": "Wizard Test",
                "invoice_date": "2026-01-27",
                "invoice_user_id": cls.env.user.id,
            }
        )
        cls.productlink = cls.Productlink.create(
            {
                "invoiceset_id": cls.invoiceset.id,
                "product_id": cls.product.id,
                "billable_item_group_field": "name",
                "billable_item_detail_desc": "Name={{ billable_item.name }}",
                "billable_item_domain": "[]",
            }
        )

    def test_default_get_reads_from_productlink(self):
        wizard_env = self.Wizard.with_context(active_id=self.productlink.id)
        defaults = wizard_env.default_get(
            [
                "billable_item_group_field",
                "billable_item_detail_desc",
                "billable_item_domain",
                "category_code",
                "editable",
            ]
        )
        self.assertEqual(defaults["billable_item_group_field"], "name")
        self.assertEqual(defaults["billable_item_domain"], "[]")
        self.assertEqual(defaults["category_code"], 10)
        self.assertTrue(defaults["editable"])

    def test_set_config_fields_writes_to_productlink(self):
        wizard = self.Wizard.with_context(active_id=self.productlink.id).create(
            {
                "billable_item_group_field": "id",
                "billable_item_detail_desc": "ID={{ billable_item.id }}",
                "billable_item_domain": "[('id','>',0)]",
            }
        )
        wizard.set_config_fields()

        self.productlink.invalidate_recordset(
            [
                "billable_item_group_field",
                "billable_item_detail_desc",
                "billable_item_domain",
            ]
        )
        self.assertEqual(self.productlink.billable_item_group_field, "id")

    def test_set_config_fields_no_active_id_closes(self):
        wizard = self.Wizard.create(
            {
                "billable_item_group_field": "id",
                "billable_item_detail_desc": "ID={{ billable_item.id }}",
                "billable_item_domain": "[]",
            }
        )
        action = wizard.set_config_fields()
        self.assertEqual(action, {"type": "ir.actions.act_window_close"})
