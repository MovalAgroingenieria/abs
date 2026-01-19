# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from unittest.mock import patch
from odoo.tests.common import new_test_user, TransactionCase, HttpCase


class TestInvoicesetBackgroundDecision(TransactionCase):

    def test_background_flag_controls_execution_mode(self):
        invoiceset = self.env["account.invoiceset"].create({
            "description": "Test set",
            "invoice_date": fields.Date.today(),
        })

        self.env["ir.config_parameter"].sudo().set_param(
            "base_invoicing.mass_invoicing_run_background",
            False,
        )

        with patch.object(
                self.env["account.invoiceset"], "calculation_process"
        ) as mocked:
            invoiceset.calculate_invoiceset()
            mocked.assert_called()
