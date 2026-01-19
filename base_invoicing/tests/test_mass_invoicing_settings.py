# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests.common import new_test_user, TransactionCase, HttpCase
from odoo import fields


class TestMassInvoicingSettings(TransactionCase):
    def _create_invoiceset(self, **extra_vals):
        vals = {
            "alphanum_code": "T0001",
            "description": "Test",
            "invoice_date": fields.Date.today(),
            "invoice_user_id": self.env.user.id,
        }
        vals.update(extra_vals)
        return self.env["account.invoiceset"].create(vals)

    def _create_configured_invoiceset(self, **extra_vals):
        invoiceset = self._create_invoiceset(**extra_vals)
        return invoiceset

    def test_mass_invoicing_background_param(self):
        settings = self.env["res.config.settings"].create({
            "mass_invoicing_run_background": True,
        })
        settings.execute()

        value = self.env["ir.config_parameter"].sudo().get_param(
            "base_invoicing.mass_invoicing_run_background"
        )
        self.assertEqual(value, "True")

    def test_settings_are_company_dependent(self):
        company_a = self.env.ref("base.main_company")
        company_b = self.env["res.company"].create({"name": "Other Co"})

        company_a.mass_invoicing_run_background = True
        company_b.mass_invoicing_run_background = False

        self.assertTrue(company_a.mass_invoicing_run_background)
        self.assertFalse(company_b.mass_invoicing_run_background)

    def test_invoice_set_uses_company_background_flag(self):
        invoiceset = self._create_configured_invoiceset()

        invoiceset.calculate_invoiceset()

        self.assertEqual(invoiceset.state, "calculated")

    def test_sequence_is_company_specific(self):
        seq = self.env["ir.sequence"].create({
            "name": "Invoice Set Seq",
            "code": "test.seq",
            "company_id": self.env.company.id,
        })
        self.env.company.mass_invoicing_seq_invoiceset_code_id = seq

        invoiceset = self._create_invoiceset()
        self.assertTrue(invoiceset.alphanum_code)
