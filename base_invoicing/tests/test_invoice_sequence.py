# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestInvoicesetSequence(TransactionCase):
    def test_invoiceset_uses_configured_sequence(self):
        company = self.env.company

        seq = self.env["ir.sequence"].create(
            {
                "name": "Invoice Set Test",
                "code": "test.invoiceset",
                "prefix": "TEST/",
                "padding": 4,
                "company_id": company.id,  # important in v18 (company-specific sequences)
            }
        )

        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "base_invoicing.mass_invoicing_seq_invoiceset_code_id",
            str(seq.id),
        )

        invoiceset = (
            self.env["account.invoiceset"]
            .with_company(company)
            .create(
                {
                    "description": "Test set",
                    "invoice_date": fields.Date.today(),
                }
            )
        )

        self.assertTrue(invoiceset.alphanum_code.startswith("TEST/"))
