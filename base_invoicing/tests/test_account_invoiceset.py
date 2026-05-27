# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountInvoiceset(TransactionCase):
    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        super().setUpClass()
        cls.Invoiceset = cls.env["account.invoiceset"]

    def _create_invoiceset(self, **vals):
        base = {
            "alphanum_code": "SET-0001",
            "description": "Demo",
            "invoice_date": "2026-01-27",
            "invoice_user_id": self.env.user.id,
        }
        base.update(vals)
        return self.Invoiceset.create(base)

    def test_compute_display_name(self):
        invset = self._create_invoiceset(alphanum_code="SET-0003", description="My set")
        self.assertEqual(invset.display_name, "SET-0003 (My set)")
        invset.write({"description": ""})
        invset.invalidate_recordset(["display_name"])
        self.assertEqual(invset.display_name, "SET-0003")

    def test_unlink_blocked_when_not_draft_or_configured(self):
        invset = self._create_invoiceset(alphanum_code="SET-0004")
        # Force stored state to calculated to test unlink guard
        invset.write({"state": "calculated"})
        with self.assertRaises(UserError):
            invset.unlink()

    def test_calculate_invoiceset_returns_warning_if_other_calculating(self):
        a = self._create_invoiceset(alphanum_code="SET-0005")
        b = self._create_invoiceset(alphanum_code="SET-0006")

        a.write({"state": "calculating"})
        b.write({"state": "configured"})

        action = b.calculate_invoiceset()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
