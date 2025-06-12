# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, SUPERUSER_ID, exceptions


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].set_param(
        'base_invoicing.mass_invoicing_seq_invoiceset_code_id',
        env.ref('base_invoicing.seq_invoiceset_code').id)
    env['ir.config_parameter'].set_param(
        'base_invoicing.mass_invoicing_run_background', False)


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env.cr.savepoint()
        env.cr.execute("""
            DELETE FROM ir_config_parameter
            WHERE key LIKE 'base_invoicing.%'""")
        env.cr.commit()
    except (Exception,):
        env.cr.rollback()
