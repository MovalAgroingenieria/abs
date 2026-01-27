# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountInvoiceset(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Invoiceset = cls.env["account.invoiceset"]
        cls.Progress = cls.env["account.invoiceset.progress"]

    def _create_invoiceset_minimal(self):
        # Requires simple.model to accept these fields; keep minimal.
        return self.Invoiceset.create(
            {
                "alphanum_code": "SET-001",
                "description": "Test set",
                "invoice_date": "2026-01-27",
                "invoice_user_id": self.env.user.id,
            }
        )

    def test_create_creates_progress_row(self):
        invset = self._create_invoiceset_minimal()
        prog = self.Progress.search([("invoiceset_id", "=", invset.id)], limit=1)
        self.assertTrue(prog, "Progress row must be created with invoice set")

    def test_display_name_computed(self):
        invset = self._create_invoiceset_minimal()
        self.assertIn("SET-001", invset.display_name)
        self.assertIn("Test set", invset.display_name)

    def test_unlink_blocked_when_not_draft_or_configured(self):
        invset = self._create_invoiceset_minimal()
        invset.write({"state": "calculated"})
        with self.assertRaises(UserError):
            invset.unlink()

    def test_unlink_allowed_in_draft(self):
        invset = self._create_invoiceset_minimal()
        invset.write({"state": "draft"})
        invset_id = invset.id
        invset.unlink()
        self.assertFalse(self.Invoiceset.browse(invset_id).exists())
