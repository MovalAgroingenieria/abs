# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import SUPERUSER_ID


def post_init_hook(env):
    """Executed right after module installation."""
    env = env(user=SUPERUSER_ID)

    params = env["ir.config_parameter"].sudo()
    params.set_param(
        "base_invoicing.mass_invoicing_seq_invoiceset_code_id",
        env.ref("base_invoicing.seq_invoiceset_code").id,
    )
    params.set_param("base_invoicing.mass_invoicing_run_background", True)

    # Ensure fees exist for partners (legacy behavior kept)
    partners = env["res.partner"].with_context(active_test=False).search([])
    partners.write({"fee_ids": [(0, 0, {})]})


def uninstall_hook(env):
    """Executed right after module uninstallation."""
    env = env(user=SUPERUSER_ID)

    params = env["ir.config_parameter"].sudo().search(
        [("key", "=like", "base_invoicing.%")]
    )
    params.unlink()
