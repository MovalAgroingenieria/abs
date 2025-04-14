# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, SUPERUSER_ID


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env.cr.savepoint()
        env.cr.execute("ALTER TABLE res_region RENAME TO res_admregion;")
        cr.execute("""
            UPDATE ir_model SET model = 'res.admregion' WHERE model =
                'res.region';
            UPDATE ir_model_fields SET model = 'res.admregion' WHERE model =
                'res.region';
            UPDATE ir_model_fields SET relation = 'res.admregion' WHERE
                relation = 'res.region';
            UPDATE ir_model_data SET model = 'res.admregion' WHERE model =
                'res.region';
        """)
        env.cr.commit()
    except Exception:
        env.cr.rollback()


