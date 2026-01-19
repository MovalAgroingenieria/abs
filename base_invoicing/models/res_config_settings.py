# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mass_invoicing_seq_invoiceset_code_id = fields.Many2one(
        comodel_name="ir.sequence",
        config_parameter="base_invoicing.mass_invoicing_seq_invoiceset_code_id",
        string="Sequence for the codes of invoice set",
    )
    mass_invoicing_run_background = fields.Boolean(
        config_parameter="base_invoicing.mass_invoicing_run_background",
        string="Calculate the invoice set in background (y/n)",
    )
