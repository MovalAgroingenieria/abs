# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import new_test_user, TransactionCase, HttpCase
from odoo import fields


class TestInvoicesetSequence(TransactionCase):

    def test_invoiceset_uses_configured_sequence(self):
        seq = self.env["ir.sequence"].create({
            "name": "Invoice Set Test",
            "code": "test.invoiceset",
            "prefix": "TEST/",
            "padding": 4,
        })

        self.env["ir.config_parameter"].sudo().set_param(
            "base_invoicing.mass_invoicing_seq_invoiceset_code_id",
            seq.id,
        )

        invoiceset = self.env["account.invoiceset"].create({
            "description": "Test set",
            "invoice_date": fields.Date.today(),
        })

        self.assertTrue(invoiceset.alphanum_code.startswith("TEST/"))
