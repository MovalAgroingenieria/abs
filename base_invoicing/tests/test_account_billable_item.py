# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountBillableItem(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        # Abstract model recordset
        cls.Billable = cls.env["account.billable.item"]

    def test_compute_groupvalue_empty_when_false(self):
        # Ensure safe conversion to empty string
        dummy = self.Billable.new({})
        dummy._compute_billing_groupvalue()
        self.assertEqual(dummy.billing_groupvalue, "")

    def test_compute_quantity_default(self):
        dummy = self.Billable.new({})
        dummy._compute_billing_quantity()
        self.assertEqual(dummy.billing_quantity, 1.0)

    def test_compute_partner_default(self):
        dummy = self.Billable.new({})
        dummy._compute_billing_partner_id()
        self.assertFalse(dummy.billing_partner_id)

    def test_inherits_from_account_billable_item_false_for_unknown(self):
        self.assertFalse(
            self.Billable.inherits_from_account_billable_item("non.existent.model")
        )

    def test_inherits_from_account_billable_item_true_for_billable_test_model(self):
        self.assertTrue(
            self.Billable.inherits_from_account_billable_item(
                "base_invoicing.billable_item_test"
            )
        )
