# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResFee(models.Model):
    _name = "res.fee"
    _description = "Fee"
    _inherits = {"res.partner": "partner_id"}
    _inherit = "account.billable.item"

    _billing_partner_id_name = "partner_id"
    _billing_quantity_name = ""

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Associated Partner",
        required=True,
        ondelete="cascade",
        auto_join=True,
        index=True,
    )

    partner_parent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Related company of partner",
        related="partner_id.parent_id",
        store=True,
        index=True,
    )
    partner_partner_share = fields.Boolean(
        string="Share partner of partner",
        related="partner_id.partner_share",
        store=True,
    )
    partner_vat = fields.Char(
        string="VAT of partner",
        related="partner_id.vat",
        store=True,
    )
    partner_email = fields.Char(
        string="Email of partner",
        related="partner_id.email",
        store=True,
    )
    partner_phone = fields.Char(
        string="Phone of partner",
        related="partner_id.phone",
        store=True,
    )
    partner_mobile = fields.Char(
        string="Mobile of partner",
        related="partner_id.mobile",
        store=True,
    )
    partner_is_company = fields.Boolean(
        string="Company (y/n)",
        related="partner_id.is_company",
        store=True,
    )
