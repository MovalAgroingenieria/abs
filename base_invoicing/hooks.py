# Copyright 2025 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    """Initialize module parameters and legacy fee records.

    In Odoo 18 the hook is called with an Environment, not (cr, registry).
    """
    env = api.Environment(env.cr, SUPERUSER_ID, dict(env.context or {}))

    params = env["ir.config_parameter"].sudo()
    params.set_param(
        "base_invoicing.mass_invoicing_seq_invoiceset_code_id",
        env.ref("base_invoicing.seq_invoiceset_code").id,
    )
    params.set_param("base_invoicing.mass_invoicing_run_background", True)

    # Legacy behavior: ensure at least one fee per partner.
    # Create fee records only for partners that do not have any.
    partners = env["res.partner"].with_context(active_test=False).sudo().search([])
    partners_without_fee = partners.filtered(lambda p: not p.fee_ids)
    if partners_without_fee:
        env["res.fee"].sudo().create(
            [{"partner_id": partner.id} for partner in partners_without_fee]
        )


def uninstall_hook(env):
    """Cleanup configuration parameters and hybrid views on uninstall."""
    env = api.Environment(env.cr, SUPERUSER_ID, dict(env.context or {}))
    params = (
        env["ir.config_parameter"].sudo().search([("key", "=like", "base_invoicing.%")])
    )
    params.unlink()

    # Drop hybrid view models (x_base_invoicing.selectable_*)
    hybrid_models = (
        env["ir.model"]
        .sudo()
        .search([("model", "=like", "x_base_invoicing.selectable_%")])
    )
    if hybrid_models:
        hybrid_models.with_context(_force_unlink=True).unlink()
