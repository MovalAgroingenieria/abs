# Copyright 2025 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    """Initialize module parameters and legacy fee records.

    In Odoo 18 the hook is called with an Environment, not (cr, registry).
    """
    env = api.Environment(env.cr, SUPERUSER_ID, dict(env.context or {}))

    # Mark account.invoiceset as supporting comment templates (base_comment_template)
    ir_model = env["ir.model"].sudo()
    for model_name in ("account.invoiceset", "account.move"):
        model = ir_model.search([("model", "=", model_name)], limit=1)
        if model and not model.is_comment_template:
            model.is_comment_template = True

    params = env["ir.config_parameter"].sudo()
    seq = env.ref("base_invoicing.seq_invoiceset_code", raise_if_not_found=False)
    if seq:
        params.set_param("base_invoicing.mass_invoicing_seq_invoiceset_code_id", seq.id)

    if seq:
        companies = (
            env["res.company"]
            .sudo()
            .search([("mass_invoicing_seq_invoiceset_code_id", "=", False)])
        )
        companies.write({"mass_invoicing_seq_invoiceset_code_id": seq.id})

    # Backfill compatible_billable_field_ids for existing field maps (new Many2many)
    field_map_model = env["product.category.invoice.line.field.map"].sudo()
    for rec in field_map_model.search([]):
        rec._update_compatible_billable_field_ids()  # pylint: disable=protected-access

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
