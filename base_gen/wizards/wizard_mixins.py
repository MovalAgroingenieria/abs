# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import models


class ActiveRecordWizardMixin(models.AbstractModel):
    _name = "wizard.active.record.mixin"
    _description = "Mixin for wizards that operate on the active record from context"

    def _get_active_record_or_empty(self, model_name):
        """Return the active record from context, or empty recordset if none."""
        active_id = self.env.context.get("active_id")
        if not active_id:
            return self.env[model_name].browse()
        return self.env[model_name].browse(active_id)
