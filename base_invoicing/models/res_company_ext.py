# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mass_invoicing_seq_invoiceset_code_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Invoice Set Sequence",
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "mass_invoicing_seq_invoiceset_code_id" in fields_list:
            seq = self.env.ref(
                "base_invoicing.seq_invoiceset_code", raise_if_not_found=False
            )
            if seq and not vals.get("mass_invoicing_seq_invoiceset_code_id"):
                vals["mass_invoicing_seq_invoiceset_code_id"] = seq.id
        return vals

    mass_invoicing_run_background = fields.Boolean(
        string="Run invoice set calculation in background",
        default=False,
    )

    mass_invoicing_progress_batch_size = fields.Integer(
        string="Invoice batch size for progress commits",
        default=50,
        help="Number of invoices per batch when committing progress in background mode. Higher = faster but less responsive progress bar.",
    )
