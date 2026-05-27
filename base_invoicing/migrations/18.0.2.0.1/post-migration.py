# Copyright 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
# pylint: disable=invalid-name,broad-exception-caught,except-pass

from odoo import SUPERUSER_ID, api
from odoo.tools import sql as odoo_sql


def migrate(cr, version):
    """Drop background-calculation artifacts and pivot view support."""
    if not version:
        return
    # Drop the progress table (model is gone)
    try:
        cr.execute("DROP TABLE IF EXISTS account_invoiceset_progress CASCADE")
    except Exception:
        pass
    # Drop obsolete res_company columns
    for col in ("mass_invoicing_run_background", "mass_invoicing_progress_batch_size"):
        try:
            cr.execute(
                odoo_sql.SQL(
                    "ALTER TABLE res_company DROP COLUMN IF EXISTS %s",
                    odoo_sql.SQL.identifier(col),
                )
            )
        except Exception:
            pass
    # Drop obsolete ir.config_parameter
    try:
        cr.execute(
            "DELETE FROM ir_config_parameter "
            "WHERE key = 'base_invoicing.mass_invoicing_run_background'"
        )
    except Exception:
        pass
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Unlink obsolete records by external id
    for xmlid in (
        "base_invoicing.account_invoiceset_cron_reset_stale_calculating",
        "base_invoicing."
        "menu_technicalactions_refresh_invoicesets_in_calculation_process",
        "base_invoicing."
        "account_invoiceset_refresh_all_invoicesets_in_calculation_process"
        "_serveraction",
    ):
        try:
            rec = env.ref(xmlid, raise_if_not_found=False)
            if rec:
                rec.unlink()
        except Exception:
            pass
    # Delete ir.ui.view records linked as pivot views
    try:
        cr.execute(
            "SELECT pivot_view_id FROM account_selectable_item_hybrid_view "
            "WHERE pivot_view_id IS NOT NULL"
        )
        pivot_ids = [row[0] for row in cr.fetchall()]
        if pivot_ids:
            env["ir.ui.view"].browse(pivot_ids).unlink()
    except Exception:
        pass
    # Drop the column from the table
    try:
        cr.execute(
            "ALTER TABLE account_selectable_item_hybrid_view "
            "DROP COLUMN IF EXISTS pivot_view_id"
        )
    except Exception:
        pass
