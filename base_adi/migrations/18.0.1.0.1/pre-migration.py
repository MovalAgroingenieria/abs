# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from psycopg2 import sql

XMLID_RENAMES = (
    ("res_admregion_view_tree", "res_admregion_view_list"),
    ("res_province_view_tree", "res_province_view_list"),
    ("res_municipality_view_tree", "res_municipality_view_list"),
    ("res_place_view_tree", "res_place_view_list"),
)


def migrate(cr, version):
    """Create compatibility xmlids for renamed list views.

    Keep legacy *_view_tree xmlids and add *_view_list aliases pointing to
    the same ir.ui.view records. This prevents duplicated views on upgrade and
    keeps old references working while dependent modules are upgraded.
    """
    for old_name, new_name in XMLID_RENAMES:
        cr.execute(
            """
            SELECT model, res_id, noupdate
              FROM ir_model_data
             WHERE module = 'base_adi' AND name = %s
             LIMIT 1
            """,
            (old_name,),
        )
        row = cr.fetchone()
        if not row:
            continue

        model, res_id, noupdate = row

        cr.execute(
            """
            SELECT 1
              FROM ir_model_data
             WHERE module = 'base_adi' AND name = %s
             LIMIT 1
            """,
            (new_name,),
        )
        if cr.fetchone():
            continue

        cr.execute(
            sql.SQL("""
                INSERT INTO ir_model_data
                    (module, name, model, res_id, noupdate)
                VALUES
                    ('base_adi', %s, %s, %s, %s)
                """),
            (new_name, model, res_id, noupdate),
        )
