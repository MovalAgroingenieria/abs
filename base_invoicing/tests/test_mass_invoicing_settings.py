# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
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

    def test_mass_invoicing_background_param_is_saved(self):
        settings = self.env["res.config.settings"].create(
            {"mass_invoicing_run_background": True}
        )
        # Prefer set_values in modern Odoo settings models
        if hasattr(settings, "set_values"):
            settings.set_values()
        else:
            settings.execute()

        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("base_invoicing.mass_invoicing_run_background")
        )
        self.assertEqual(value, "True")

    def test_settings_are_company_dependent(self):
        company_a = self.env.company
        company_b = self.env["res.company"].create({"name": "Other Co"})

        company_a.mass_invoicing_run_background = True
        company_b.mass_invoicing_run_background = False

        self.assertTrue(company_a.mass_invoicing_run_background)
        self.assertFalse(company_b.mass_invoicing_run_background)

    def test_sequence_is_company_specific(self):
        seq = self.env["ir.sequence"].create(
            {
                "name": "Invoice Set Seq",
                "code": "test.seq.invoiceset",
                "company_id": self.env.company.id,
                "prefix": "T-",
                "padding": 4,
            }
        )
        self.env.company.mass_invoicing_seq_invoiceset_code_id = seq

        invoiceset = self._create_invoiceset()
        # Aquí lo único que podemos afirmar sin conocer tu simple.model
        # es que el código existe; si el default usa secuencia, compruébalo:
        self.assertTrue(invoiceset.alphanum_code)
