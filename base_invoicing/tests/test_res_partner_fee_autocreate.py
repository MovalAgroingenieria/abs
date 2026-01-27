# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestResPartnerFeeAutocreate(TransactionCase):
    def test_fee_is_created_on_partner_create(self):
        partner = self.env["res.partner"].create({"name": "Partner Fee Test"})
        self.assertTrue(partner.fee_ids, "A default fee should be created for partner")
        self.assertEqual(len(partner.fee_ids), 1)

    def test_fee_is_not_created_when_context_skip(self):
        partner = (
            self.env["res.partner"]
            .with_context(skip_fee_autocreate=True)
            .create({"name": "Partner Fee Skip"})
        )
        self.assertFalse(partner.fee_ids, "Fee must not be auto-created when skipped")

    def test_no_duplicate_fee_if_fee_already_exists(self):
        fee_model = self.env["res.fee"]
        partner = (
            self.env["res.partner"]
            .with_context(skip_fee_autocreate=True)
            .create({"name": "Partner Fee Existing"})
        )
        fee_model.create({"partner_id": partner.id})

        # Call helper explicitly (simulates re-run / repair job)
        partner._ensure_default_fee()
        self.assertEqual(len(partner.fee_ids), 1, "Must not create duplicate fees")
