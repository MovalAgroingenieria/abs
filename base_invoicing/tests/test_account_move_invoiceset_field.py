# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestAccountMoveInvoicesetField(TransactionCase):
    def test_invoiceset_field_metadata(self):
        field = self.env["account.move"]._fields["invoiceset_id"]
        self.assertEqual(field.type, "many2one")
        self.assertEqual(field.comodel_name, "account.invoiceset")
        self.assertTrue(field.index)
        self.assertFalse(field.copy)
        self.assertTrue(field.readonly)
