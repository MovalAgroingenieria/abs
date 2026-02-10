# Copyright 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
# pylint: disable=invalid-name,broad-exception-caught,except-pass

from odoo import SUPERUSER_ID, api
from odoo.tools import sql as odoo_sql


def migrate(cr, version):
    """Remove legacy hybrid views (without category_id) and their artifacts.

    Hybrid views are now keyed by (billable_model_id, category_id).
    Old records without category_id are removed; they will be recreated on demand.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    hybrid_model = env["account.selectable.item.hybrid.view"].with_context(
        active_test=False
    )
    legacy = hybrid_model.search([("category_id", "=", False)])
    if not legacy:
        return

    for rec in legacy:
        # Drop PostgreSQL view
        if rec.view_table:
            try:
                drop_sql = odoo_sql.SQL(
                    "DROP VIEW IF EXISTS %s CASCADE",
                    odoo_sql.SQL.identifier(rec.view_table),
                )
                env.cr.execute(drop_sql)
            except Exception:
                pass

        # Unlink ir.model (cascades to fields, views, actions)
        if rec.model_id:
            try:
                rec.model_id.with_context(_force_unlink=True).unlink()
            except Exception:
                pass

    legacy.unlink()
