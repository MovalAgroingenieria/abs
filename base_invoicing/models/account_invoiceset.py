# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=unused-argument
# pylint: disable=protected-access
# pylint: disable=duplicate-code
# pylint: disable=no-raise-unlink
# pylint: disable=translation-not-lazy
# pylint: disable=translation-positional-used
# pylint: disable=too-many-lines
# pylint: disable=except-pass
# pylint: disable=broad-exception-caught

import logging
import traceback
from collections import defaultdict

from jinja2 import Template, TemplateError
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.sql import SQL

_logger = logging.getLogger(__name__)


class AccountInvoiceset(models.Model):  # pylint: disable=R0904
    _name = "account.invoiceset"
    _description = "Invoice Set"
    _inherit = ["simple.model", "mail.thread", "comment.template"]
    _order = "alphanum_code desc"

    # simple.model v18 uses these attribute names (no leading underscore)
    set_num_code = False
    sequence_for_codes = "base_invoicing.mass_invoicing_seq_invoiceset_code_id"
    size_name = 20
    minlength = 0
    maxlength = 20
    allowed_blanks_in_code = False
    set_alphanum_code_to_lowercase = False
    set_alphanum_code_to_uppercase = True
    size_description = 100

    alphanum_code = fields.Char(
        string="Code of invoice set",
        required=True,
        tracking=True,
    )
    description = fields.Char(
        string="Description of invoice set",
        required=True,
        translate=True,
        tracking=True,
    )
    invoice_date = fields.Date(
        string="Invoicing Date",
        default=fields.Date.context_today,
        required=True,
        index=True,
        tracking=True,
    )
    invoice_date_due = fields.Date(string="Due Date", tracking=True)
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        tracking=True,
    )
    journal_type = fields.Selection(
        string="Journal type",
        selection=[("sale", "Sale"), ("purchase", "Purchase")],
        compute="_compute_journal_type",
        help="Used to filter journals by invoice type "
        "(sale for customer, purchase for vendor).",
    )
    payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        tracking=True,
    )
    invoice_user_id = fields.Many2one(
        string="Sales Person",
        comodel_name="res.users",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    invoice_type = fields.Selection(
        selection=[
            ("customer", "Customer"),
            ("supplier", "Vendor"),
        ],
        default="customer",
        required=True,
        tracking=True,
        help="Customer: sales invoices (and customer refunds "
        "if total is negative). "
        "Vendor: vendor bills (and vendor refunds "
        "if total is negative). "
        "Alternative: a separate model or type on productlink "
        "could allow mixing customer and vendor lines in one "
        "set; the current design keeps one type per set.",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("configured", "Configured"),
            ("calculating", "In progress"),
            ("calculated", "Calculated"),
            ("committed", "Committed"),
            ("error", "Error"),
        ],
        default="draft",
        store=True,
        compute="_compute_state",
        inverse="_inverse_state",
        index=True,
        tracking=True,
    )
    calculation_started_at = fields.Datetime(
        string="Calculation started at",
        readonly=True,
        help="Set when state enters 'calculating'; used to detect stale processes.",
    )
    calculation_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Calculation triggered by",
        readonly=True,
        copy=False,
    )
    calculation_finished_at = fields.Datetime(
        string="Calculation finished at",
        readonly=True,
    )
    calculation_speed_inv_per_sec = fields.Float(
        string="Calculation speed (invoices/sec)",
        readonly=True,
    )
    calculation_duration_display = fields.Char(
        string="Calculation duration",
        compute="_compute_calculation_duration_display",
    )
    last_calculation_error = fields.Text(
        string="Last calculation error",
        readonly=True,
        copy=False,
        help="Traceback or message of the last error raised during the "
        "invoice generation process. Cleared when a new calculation starts.",
    )
    queue_job_id = fields.Many2one(
        comodel_name="queue.job",
        string="Background calculation job",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Internal reference to the background job currently calculating "
        "(or that last calculated) this invoice set.",
    )

    move_ids = fields.One2many(
        string="Invoices",
        comodel_name="account.move",
        inverse_name="invoiceset_id",
        copy=False,
    )
    number_of_invoices = fields.Integer(
        string="Number of invoices",
        store=True,
        compute="_compute_number_of_invoices",
    )
    number_of_invoice_lines = fields.Integer(
        string="Number of invoice lines",
        compute="_compute_number_of_invoice_lines",
    )
    selectable_item_count = fields.Integer(
        string="Selectable items count",
        compute="_compute_selectable_item_count",
    )
    productlink_summary = fields.Char(
        string="Products (selected)",
        compute="_compute_productlink_summary",
        help="Summary of products with selected quantities for kanban display.",
    )
    move_line_ids = fields.One2many(
        string="Invoice Lines",
        comodel_name="account.move.line",
        inverse_name="invoiceset_id",
    )
    productlink_ids = fields.One2many(
        string="Invoice-Set Lines",
        comodel_name="account.invoiceset.productlink",
        inverse_name="invoiceset_id",
    )

    all_productlinks_configured = fields.Boolean(
        string="All product-links are configured",
        default=False,
        store=True,
        compute="_compute_all_productlinks_configured",
    )
    invoice_generation_progress = fields.Float(
        string="Percentage of progress during invoice generation",
        default=0.0,
        readonly=True,
    )
    calculated = fields.Boolean(
        string="Is calculated",
        default=False,
        required=True,
        readonly=True,
    )
    some_posted_invoice = fields.Boolean(
        string="Some posted invoice",
        default=False,
        store=True,
        compute="_compute_some_posted_invoice",
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        default=lambda self: self.env.company.partner_id,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    amount_total_invoices = fields.Monetary(
        string="Total Amount (draft + validated)",
        compute="_compute_amount_total_invoices",
        currency_field="company_currency_id",
    )
    amount_total_posted = fields.Monetary(
        string="Validated Amount",
        compute="_compute_amount_total_posted",
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
    )
    number_of_invoices_draft = fields.Integer(
        string="Invoices to validate",
        compute="_compute_number_of_invoices_draft",
    )
    number_of_invoices_posted = fields.Integer(
        string="Validated invoices",
        compute="_compute_number_of_invoices_posted",
    )
    number_of_invoices_cancelled = fields.Integer(
        string="Cancelled invoices",
        compute="_compute_number_of_invoices_cancelled",
    )

    # -------------------------------------------------------------------------
    # Display name (name_get deprecated in 17+)
    # -------------------------------------------------------------------------

    @api.depends("alphanum_code", "description")
    def _compute_display_name(self):
        for record in self:
            code = record.alphanum_code or ""
            desc = record.description or ""
            record.display_name = f"{code} ({desc})" if desc else code

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends("all_productlinks_configured", "some_posted_invoice")
    def _compute_state(self):
        """Auto-transition draft<->configured and calculated<->committed.

        States 'calculating' and 'error' are managed explicitly by the
        invoice generation process, not by this computed field.
        """
        for record in self:
            state = record.state
            if state in ("calculating", "error"):
                # Preserve — only the generation process or user action
                # should change these states.
                pass
            elif state == "draft" and record.all_productlinks_configured:
                state = "configured"
            elif state == "configured" and not record.all_productlinks_configured:
                state = "draft"
            elif state == "calculated" and record.some_posted_invoice:
                state = "committed"
            elif state == "committed" and not record.some_posted_invoice:
                state = "calculated"
            record.state = state

    def _inverse_state(self):
        """Allow direct writes to state (e.g. calculating, calculated)."""

    @api.depends("move_ids")
    def _compute_number_of_invoices(self):
        # Batch-friendly using read_group
        data = self.env["account.move"].read_group(
            [("invoiceset_id", "in", self.ids)],
            ["invoiceset_id"],
            ["invoiceset_id"],
        )
        mapped = {d["invoiceset_id"][0]: d["invoiceset_id_count"] for d in data}
        for record in self:
            record.number_of_invoices = mapped.get(record.id, 0)

    @api.depends("move_line_ids")
    def _compute_number_of_invoice_lines(self):
        data = self.env["account.move.line"].read_group(
            [("invoiceset_id", "in", self.ids)],
            ["invoiceset_id"],
            ["invoiceset_id"],
        )
        mapped = {d["invoiceset_id"][0]: d["invoiceset_id_count"] for d in data}
        for record in self:
            record.number_of_invoice_lines = mapped.get(record.id, 0)

    @api.depends(
        "productlink_ids",
        "productlink_ids.product_id",
        "productlink_ids.selected_item_ids",
        "productlink_ids.lst_price",
        "productlink_ids.product_id.product_tmpl_id.name",
    )
    def _compute_productlink_summary(self):
        for record in self:
            parts = []
            for pl in record.productlink_ids:
                if not pl.product_id:
                    continue
                name = pl.product_id.product_tmpl_id.name or pl.product_id.display_name
                qty = pl.number_of_selected_items or 0
                price = pl.lst_price
                if price and price != 0:
                    parts.append(f"{name} ({qty} @ {price:.2f})")
                else:
                    parts.append(f"{name} ({qty})")
            record.productlink_summary = ", ".join(parts) if parts else ""

    @api.depends("productlink_ids", "productlink_ids.selectable_item_ids")
    def _compute_selectable_item_count(self):
        for record in self:
            record.selectable_item_count = self.env[
                "account.selectable.item"
            ].search_count([("productlink_id.invoiceset_id", "=", record.id)])

    @api.depends(
        "productlink_ids", "productlink_ids.populated", "productlink_ids.display_type"
    )
    def _compute_all_productlinks_configured(self):
        for record in self:
            product_productlinks = record.productlink_ids.filtered(
                lambda p: p.display_type == "product"
            )
            record.all_productlinks_configured = bool(product_productlinks) and all(
                pl.populated for pl in product_productlinks
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_some_posted_invoice(self):
        for record in self:
            record.some_posted_invoice = any(
                m.state == "posted" for m in record.move_ids
            )

    @api.depends("move_ids", "move_ids.amount_total_signed", "move_ids.state")
    def _compute_amount_total_invoices(self):
        for record in self:
            total = sum(
                m.amount_total_signed for m in record.move_ids if m.state != "cancel"
            )
            record.amount_total_invoices = total

    @api.depends("move_ids", "move_ids.amount_total_signed", "move_ids.state")
    def _compute_amount_total_posted(self):
        for record in self:
            record.amount_total_posted = sum(
                m.amount_total_signed for m in record.move_ids if m.state == "posted"
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_number_of_invoices_draft(self):
        for record in self:
            record.number_of_invoices_draft = sum(
                1 for m in record.move_ids if m.state == "draft"
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_number_of_invoices_posted(self):
        for record in self:
            record.number_of_invoices_posted = sum(
                1 for m in record.move_ids if m.state == "posted"
            )

    @api.depends("move_ids", "move_ids.state")
    def _compute_number_of_invoices_cancelled(self):
        for record in self:
            record.number_of_invoices_cancelled = sum(
                1 for m in record.move_ids if m.state == "cancel"
            )

    @api.depends("calculation_started_at", "calculation_finished_at")
    def _compute_calculation_duration_display(self):
        for record in self:
            if record.calculation_started_at and record.calculation_finished_at:
                delta = record.calculation_finished_at - record.calculation_started_at
                total_sec = int(delta.total_seconds())
                if total_sec < 60:
                    record.calculation_duration_display = f"{total_sec}s"
                elif total_sec < 3600:
                    m, s = divmod(total_sec, 60)
                    record.calculation_duration_display = f"{m}m {s}s"
                else:
                    h, r = divmod(total_sec, 3600)
                    m, s = divmod(r, 60)
                    record.calculation_duration_display = f"{h}h {m}m {s}s"
            else:
                record.calculation_duration_display = ""

    @api.depends("invoice_type")
    def _compute_journal_type(self):
        for record in self:
            record.journal_type = (
                "sale" if record.invoice_type == "customer" else "purchase"
            )

    @api.onchange("invoice_type")
    def _onchange_invoice_type_clear_journal(self):
        """Clear journal if it no longer matches (sale vs purchase)."""
        if self.journal_id and self.journal_type:
            if self.journal_id.type != self.journal_type:
                self.journal_id = False

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id") and vals.get("journal_id"):
                journal = self.env["account.journal"].browse(vals["journal_id"])
                if journal.exists():
                    vals["company_id"] = journal.company_id.id
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("alphanum_code") or vals.get("alphanum_code") == "/":
                # Use same sequence as "Create new": company first, else config param
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                seq = company.mass_invoicing_seq_invoiceset_code_id
                if seq and not seq.exists():
                    seq = self.env["ir.sequence"]
                if not seq and self.sequence_for_codes:
                    seq = self._get_sequence(self.sequence_for_codes)
                if not seq:
                    seq = self.env.ref(
                        "base_invoicing.seq_invoiceset_code", raise_if_not_found=False
                    )
                if seq:
                    vals["alphanum_code"] = seq.next_by_id()
        return super().create(vals_list)

    def copy_data(self, default=None):
        default = dict(default or {})
        # Force new code: exclude from copy so create() generates next sequence
        default.setdefault("alphanum_code", False)
        default.setdefault("calculation_started_at", False)
        default.setdefault("calculation_finished_at", False)
        default.setdefault("calculation_speed_inv_per_sec", 0.0)
        default.setdefault("invoice_generation_progress", 0.0)
        return super().copy_data(default)

    def copy(self, default=None):
        default = dict(default or {})
        default["alphanum_code"] = False  # Triggers sequence in create()
        default["calculation_started_at"] = False
        default["calculation_finished_at"] = False
        default["calculation_speed_inv_per_sec"] = 0.0
        default["invoice_generation_progress"] = 0.0
        new_invoiceset = super().copy(default)
        for pl in new_invoiceset.productlink_ids:
            pl.selectable_item_ids.unlink()
            pl.write({"populated": False})
        return new_invoiceset

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "configured"):
                raise UserError(
                    self.env._(
                        "It is not possible to delete a"
                        " calculated invoice set, you must cancel it first."
                    )
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _get_invoice_action_views_and_context(self):
        """Return views and context for invoice actions."""
        self.ensure_one()
        if self.invoice_type == "supplier":
            tree_view = self.env.ref("base_invoicing.view_in_invoice_tree")
            default_move_type = "in_invoice"
        else:
            tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
            default_move_type = "out_invoice"
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
        return tree_view, form_view, search_view, default_move_type

    def action_show_invoices(self):
        self.ensure_one()
        tree_view, form_view, search_view, default_move_type = (
            self._get_invoice_action_views_and_context()
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [("invoiceset_id", "=", self.id)],
            "context": {"default_move_type": default_move_type},
        }

    def action_open_queue_job(self):
        """Open the queue.job linked to this invoiceset (technical view)."""
        self.ensure_one()
        if not self.queue_job_id:
            raise UserError(
                self.env._("There is no background job linked to this invoice set.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Calculation Job"),
            "res_model": "queue.job",
            "res_id": self.queue_job_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_show_invoice_lines(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.account_move_line_view_list")
        search_view = self.env.ref("base_invoicing.account_move_line_view_search")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoice Lines"),
            "res_model": "account.move.line",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [("invoiceset_id", "=", self.id)],
            "context": {
                "create": False,
                "search_default_grouped_by_invoiceset_id": 1,
            },
        }

    def action_show_selectable_items(self):
        self.ensure_one()
        ctx = {"create": False}
        pl_ids = self.productlink_ids.ids
        if not pl_ids:
            return self._action_show_selectable_items_fallback(ctx, pl_ids)

        # Use hybrid if all productlinks share the same category with billable config
        categories = self.productlink_ids.mapped("categ_id")
        categories = categories.filtered(lambda c: c and c.billable_item_model_id)
        if len(categories) == 1:
            hybrid = self.env[
                "account.selectable.item.hybrid.view"
            ]._get_or_create_for_category(categories)
            if (
                hybrid
                and hybrid.model_id
                and hybrid.tree_view_id
                and hybrid.search_view_id
            ):
                hybrid_domain = [("x_productlink_id", "in", pl_ids)]
                if self.state not in ("draft", "configured"):
                    hybrid_domain.append(("x_selected", "=", True))
                views = [(hybrid.tree_view_id.id, "list")]
                ctx["selectable_items_categ_id"] = categories.id
                return {
                    "type": "ir.actions.act_window",
                    "name": self.env._("Selectable Items"),
                    "res_model": hybrid.model_name,
                    "view_mode": "list",
                    "views": views,
                    "search_view_id": hybrid.search_view_id.id,
                    "target": "current",
                    "domain": hybrid_domain,
                    "context": ctx,
                }

        return self._action_show_selectable_items_fallback(ctx, pl_ids)

    def _action_show_selectable_items_fallback(self, ctx, pl_ids):
        """Fallback to account.selectable.item when hybrid not applicable."""
        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")
        first_pl = self.productlink_ids[:1]
        if first_pl.categ_id:
            ctx["selectable_items_categ_id"] = first_pl.categ_id.id
        domain = [("productlink_id.invoiceset_id", "=", self.id)] if self.id else []
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Selectable Items"),
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": domain,
            "context": ctx,
        }

    def action_show_invoices_pending_validation(self):
        self.ensure_one()
        tree_view, form_view, search_view, default_move_type = (
            self._get_invoice_action_views_and_context()
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices to Validate"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [
                ("invoiceset_id", "=", self.id),
                ("state", "=", "draft"),
            ],
            "context": {"default_move_type": default_move_type},
        }

    def action_show_invoices_posted(self):
        self.ensure_one()
        tree_view, form_view, search_view, default_move_type = (
            self._get_invoice_action_views_and_context()
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Validated Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [
                ("invoiceset_id", "=", self.id),
                ("state", "=", "posted"),
            ],
            "context": {"default_move_type": default_move_type},
        }

    def action_show_invoices_cancelled(self):
        self.ensure_one()
        tree_view, form_view, search_view, default_move_type = (
            self._get_invoice_action_views_and_context()
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Cancelled Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [
                ("invoiceset_id", "=", self.id),
                ("state", "=", "cancel"),
            ],
            "context": {"default_move_type": default_move_type},
        }

    # -------------------------------------------------------------------------
    # Calculation entrypoints (queue_job background)
    # -------------------------------------------------------------------------

    # Number of invoices created per DB transaction. Small enough to give
    # frequent progress updates and bounded memory; large enough to amortize
    # ORM batch-create overhead. Tune from XML/job_function if needed.
    INVOICE_CHUNK_SIZE = 100

    # Context flags used to avoid mail/tracking overhead during mass creation.
    # Subclasses may override to add or remove flags.
    _MASS_CREATE_CONTEXT = {
        "mail_create_nolog": True,
        "mail_create_nosubscribe": True,
        "mail_notrack": True,
        "tracking_disable": True,
    }

    def calculate_invoiceset(self):
        """Atomically claim the invoiceset and enqueue a queue_job that
        generates its invoices in the background. Opens the queue.job
        record so the user can monitor progress and errors.
        """
        self.ensure_one()
        if self.state not in ("configured", "error"):
            return None
        # Atomic claim: only one transaction can flip the state from
        # configured/error -> calculating. Commit immediately so other
        # sessions see 'calculating' and bail out via UserError.
        self.env.cr.execute(
            """
            UPDATE account_invoiceset
               SET state = 'calculating',
                   calculation_started_at = NOW() AT TIME ZONE 'UTC',
                   calculation_finished_at = NULL,
                   calculation_speed_inv_per_sec = 0.0,
                   last_calculation_error = NULL,
                   calculation_user_id = %s,
                   invoice_generation_progress = 0.0,
                   write_date = NOW() AT TIME ZONE 'UTC',
                   write_uid = %s
             WHERE id = %s
               AND state IN ('configured', 'error')
            RETURNING id
            """,
            (self.env.uid, self.env.uid, self.id),
        )
        if not self.env.cr.fetchone():
            raise UserError(
                self.env._(
                    "Another user is already calculating this invoice set, "
                    "or it is not in a state that allows calculation. "
                    "Please refresh the page and try again."
                )
            )
        self.env.cr.commit()  # pylint: disable=invalid-commit
        self.env.invalidate_all()
        # Clean non-selected selectable items for this invoiceset (cheap).
        self.env.execute_query(
            SQL(
                """
                DELETE
                  FROM account_selectable_item
                 WHERE NOT selected
                   AND productlink_id IN (
                         SELECT id
                           FROM account_invoiceset_productlink
                          WHERE invoiceset_id = %s
                   )
                """,
                self.id,
            )
        )
        # Enqueue the heavy work as a queue_job. identity_key prevents
        # double-enqueueing the same invoiceset if the user clicks twice.
        # The job is opaque to the user: they only see the invoiceset.
        job = self.with_delay(
            description=self.env._(
                "Calculate invoiceset %(code)s", code=self.alphanum_code
            ),
            max_retries=3,
            identity_key=f"calculate_invoiceset_{self.id}",
        ).invoice_generation(self.id)
        queue_job_rec = job.db_record()
        if queue_job_rec:
            # Persist the link via raw SQL + commit so the queue_job hooks
            # (which run in their own transaction) can find the invoiceset.
            self.env.cr.execute(
                "UPDATE account_invoiceset SET queue_job_id = %s WHERE id = %s",
                (queue_job_rec.id, self.id),
            )
            self.env.cr.commit()  # pylint: disable=invalid-commit
            self.env.invalidate_all()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    @api.model
    def calculate_all_configured_invoiceset(self):
        """Cron entry point: enqueue a job for every 'configured' invoiceset."""
        for invoiceset in self.search([("state", "=", "configured")]):
            try:
                invoiceset.calculate_invoiceset()
            except UserError:
                # Already being calculated (or someone else claimed it).
                continue

    # -------------------------------------------------------------------------
    # Core generation (runs inside a queue_job; chunked + resumable)
    # -------------------------------------------------------------------------

    @api.model
    # pylint: disable=too-many-locals
    def invoice_generation(self, invoiceset_id, from_cron=False):
        """Generate draft invoices for ``invoiceset_id`` in chunks.

        Designed to run inside a queue_job:
        - Splits the work in chunks of ``INVOICE_CHUNK_SIZE`` and commits
          after each one. This bounds the transaction size, surfaces
          progress, and persists partial work so a retry can resume.
        - **Resumable**: ``invoice_data`` is sorted deterministically; on
          retry the number of moves already linked to the invoiceset is
          used as offset, so already-created invoices are skipped.
        - On exception, rolls back the in-flight chunk, persists the
          traceback in ``last_calculation_error``, and re-raises so that
          queue_job records the failure and triggers a retry (up to
          ``max_retries`` declared when enqueued).
        """
        invoiceset = self.browse(invoiceset_id)
        if not invoiceset.exists() or invoiceset.state != "calculating":
            # User cancelled (or someone else finished) before we started.
            _logger.info(
                "[invoiceset %s] skipped: state is not 'calculating'.",
                invoiceset_id,
            )
            return None
        code = invoiceset.alphanum_code or invoiceset_id
        _logger.info("[invoiceset %s] background generation: START", code)
        started_at = invoiceset.calculation_started_at or fields.Datetime.now()
        try:
            invoice_data = self.get_invoice_data(invoiceset) or []
            # Deterministic order so retries can resume by offset.
            invoice_data.sort(key=lambda d: d.get("invoice_key", ""))
            total = len(invoice_data)
            # How many invoices already exist (from a previous attempt).
            existing_count = self.env["account.move"].search_count(
                [("invoiceset_id", "=", invoiceset_id)]
            )
            _logger.info(
                "[invoiceset %s] data ready: %s invoices to create, "
                "%s already created (resuming).",
                code,
                total,
                existing_count,
            )
            if existing_count > total:
                # Defensive: previous run left more moves than the data
                # currently produces (e.g. selectable items changed).
                # Skip generation; finalize with current count.
                self._finalize_calculation(invoiceset, existing_count, started_at)
                return None
            if existing_count:
                invoiceset.message_post(
                    body=self.env._(
                        "Calculation Process: resuming from %(n)s/%(t)s",
                        n=existing_count,
                        t=total,
                    )
                )
            else:
                invoiceset.message_post(body=self.env._("Calculation Process: start"))

            remaining = invoice_data[existing_count:]
            done = existing_count
            chunk_size = self.INVOICE_CHUNK_SIZE
            n_chunks = (len(remaining) + chunk_size - 1) // chunk_size
            chunk_started_at = fields.Datetime.now()
            for offset in range(0, len(remaining), chunk_size):
                # Bail out if the user cancelled meanwhile.
                invoiceset.invalidate_recordset(["state"])
                if invoiceset.state != "calculating":
                    _logger.info(
                        "[invoiceset %s] no longer in 'calculating' "
                        "(now %s); aborting background generation.",
                        code,
                        invoiceset.state,
                    )
                    return None
                chunk = remaining[offset : offset + chunk_size]
                chunk_idx = offset // chunk_size + 1
                self._create_invoices_batch(invoiceset, chunk)
                done += len(chunk)
                self._update_progress(invoiceset_id, done, total)
                # Clear scheduled ORM recomputations on the invoiceset
                # (e.g. number_of_invoices) before committing. If we let
                # flush() UPDATE the invoiceset row, it conflicts with the
                # browser's concurrent web_read (SerializationFailure).
                # These fields will be recomputed at finalization or on
                # next access after the job finishes.
                self._clear_invoiceset_recompute(invoiceset)
                # Commit each chunk: bounds the transaction, releases locks,
                # makes work resumable, and lets queue_job report progress.
                self.env.cr.commit()  # pylint: disable=invalid-commit
                now = fields.Datetime.now()
                elapsed = (now - chunk_started_at).total_seconds()
                chunk_started_at = now
                rate = len(chunk) / elapsed if elapsed > 0 else 0.0
                _logger.info(
                    "[invoiceset %s] chunk %s/%s done: %s/%s invoices "
                    "(%.1f inv/s, last chunk %.1fs)",
                    code,
                    chunk_idx,
                    n_chunks,
                    done,
                    total,
                    rate,
                    elapsed,
                )

            self._finalize_calculation(invoiceset, done, started_at)
            _logger.info(
                "[invoiceset %s] background generation: DONE (%s invoices)",
                code,
                done,
            )
        except Exception as err:
            _logger.exception(
                "Error in invoice generation for invoiceset %s", invoiceset_id
            )
            tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            # Drop the in-flight chunk; persist the traceback so the user
            # can read it from the form even before the queue_job UI loads.
            # Leave state='calculating': a retry should resume cleanly,
            # and the queue.job record carries the failure status.
            self.env.cr.rollback()
            self.env.cr.execute(
                """
                UPDATE account_invoiceset
                   SET last_calculation_error = %s,
                       write_date = NOW() AT TIME ZONE 'UTC',
                       write_uid = %s
                 WHERE id = %s
                """,
                (tb, self.env.uid, invoiceset_id),
            )
            self.env.cr.commit()  # pylint: disable=invalid-commit
            # Re-raise so queue_job marks the job as failed and (if retries
            # remain) re-enqueues it. UserError/ValidationError are not
            # retried by queue_job — that's the desired semantics for data
            # errors that won't fix themselves.
            raise
        return None

    @api.model
    def _update_progress(self, invoiceset_id, done, total):
        """Write progress (0-100) via raw SQL: no recomputes, no chatter.

        Uses a SAVEPOINT so that a concurrent-read serialization conflict
        (common in --workers=0 where browser reads happen in the same
        process) does NOT abort the main transaction. Progress is cosmetic;
        if the UPDATE fails, we simply skip it.
        """
        pct = (100.0 * done / total) if total else 0.0
        try:
            self.env.cr.execute("SAVEPOINT _update_progress")
            self.env.cr.execute(
                """
                UPDATE account_invoiceset
                   SET invoice_generation_progress = %s,
                       write_date = NOW() AT TIME ZONE 'UTC',
                       write_uid = %s
                 WHERE id = %s
                """,
                (pct, self.env.uid, invoiceset_id),
            )
            self.env.cr.execute("RELEASE SAVEPOINT _update_progress")
        except Exception:  # noqa: BLE001
            self.env.cr.execute("ROLLBACK TO SAVEPOINT _update_progress")
            _logger.debug(
                "[invoiceset %s] progress update skipped (concurrent access)",
                invoiceset_id,
            )

    @api.model
    def _clear_invoiceset_recompute(self, invoiceset):
        """Remove pending ORM recomputations for stored computed fields on
        the invoiceset record.

        When we create moves with ``invoiceset_id``, the ORM schedules
        recomputation of ``number_of_invoices`` (and potentially other stored
        fields). If we let ``cr.commit()`` flush that UPDATE to the
        ``account_invoiceset`` row, it will conflict with any concurrent
        transaction reading the same row (e.g. the browser's ``web_read``),
        causing a SerializationFailure.

        By clearing the recompute queue, we skip the flush-time UPDATE.
        The fields will be recomputed naturally on next ORM access.
        """
        for field in invoiceset._fields.values():
            if field.compute and field.store:
                self.env.remove_to_compute(field, invoiceset)

    @api.model
    def _finalize_calculation(self, invoiceset, count, started_at):
        """Write final state + speed + 100% progress and post chatter."""
        finished_at = fields.Datetime.now()
        duration_sec = (finished_at - started_at).total_seconds()
        speed = count / duration_sec if duration_sec and duration_sec > 0 else 0.0
        final_state = "calculated" if count else "configured"
        invoiceset.write(
            {
                "state": final_state,
                "calculation_finished_at": finished_at,
                "calculation_speed_inv_per_sec": round(speed, 2),
                "invoice_generation_progress": 100.0,
            }
        )
        # Force recomputation of number_of_invoices (was cleared during
        # chunked generation to avoid SerializationFailure).
        invoiceset._compute_number_of_invoices()
        invoiceset.message_post(
            body=self.env._("Calculation Process: end. No. of invoices: %(n)s", n=count)
        )

    # -------------------------------------------------------------------------
    # Invoice data extraction (no runtime class mutation)
    # -------------------------------------------------------------------------

    @api.model
    def get_invoice_data(self, invoiceset):
        _logger.info(
            "[invoiceset %s] get_invoice_data: building from %s product-links",
            invoiceset.alphanum_code or invoiceset.id,
            len(invoiceset.productlink_ids),
        )
        t0 = fields.Datetime.now()
        if not self._pre_get_invoice_data(invoiceset):
            return None
        invoice_data = self._get_invoice_data(invoiceset)
        result = self._post_get_invoice_data(invoiceset, invoice_data)
        elapsed = (fields.Datetime.now() - t0).total_seconds()
        _logger.info(
            "[invoiceset %s] get_invoice_data: %s entries built in %.2fs",
            invoiceset.alphanum_code or invoiceset.id,
            len(result or []),
            elapsed,
        )
        return result

    @api.model
    def _pre_get_invoice_data(self, invoiceset):
        return True

    @api.model
    def _post_get_invoice_data(self, invoiceset, invoice_data):
        return invoice_data

    @api.model
    def _get_invoice_data(
        self, invoiceset
    ):  # noqa: C901  # pylint: disable=R0912,R0914,R0915,R1702
        invoice_data_raw = []
        for productlink in invoiceset.productlink_ids.sorted("sequence"):
            if productlink.display_type in ("line_section", "line_note"):
                continue
            if not productlink.billable_item_model_id:
                continue
            model_name = productlink.sudo().billable_item_model_id.model
            model_billable_item = self.env[model_name]
            quantity_field = productlink.billable_item_quantity_field
            group_field = productlink.billable_item_group_field
            partner_field = getattr(
                model_billable_item, "_billing_partner_id_name", "partner_id"
            )
            for selected_item in productlink.selected_item_ids:
                billable_item = model_billable_item.browse(
                    selected_item.billable_item_res_id
                )
                if not billable_item:
                    continue
                partner = getattr(billable_item, partner_field, False)
                partner_id = partner.id if partner else False
                quantity = (
                    getattr(billable_item, quantity_field, 0.0)
                    if quantity_field
                    else 1.0
                )
                ratio = productlink.billable_item_quantity_ratio or 1.0
                if ratio != 1.0:
                    quantity *= ratio
                groupvalue = (
                    str(getattr(billable_item, group_field, "")) if group_field else ""
                )
                if not partner_id or quantity == 0:
                    continue
                invoice_key = str(partner_id)
                if groupvalue:
                    invoice_key = f"{invoice_key}-{groupvalue}"
                factor = productlink.product_id.product_tmpl_id.factor_quantity
                if factor and factor != 1:
                    quantity *= factor
                vals = {
                    "partner_id": partner_id,
                    "invoice_key": invoice_key,
                    "product_id": productlink.product_id.id,
                    "quantity": quantity,
                    "billable_item_model": model_name,
                    "billable_item_res_id": billable_item.id,
                    "_productlink": productlink,
                    "_groupvalue": groupvalue,
                }
                invoice_data_raw.append(vals)
        if not invoice_data_raw:
            return []
        # Group product lines by (invoice_key, productlink_id)
        by_key_pl = defaultdict(lambda: defaultdict(list))
        for item in invoice_data_raw:
            pl = item.get("_productlink")
            if pl:
                by_key_pl[item["invoice_key"]][pl.id].append(item)
        # Build ordered lines per invoice: follow productlink
        # sequence, inject section/note
        result = []
        productlinks_ordered = invoiceset.productlink_ids.sorted("sequence")
        for invoice_key in by_key_pl:
            partner_id = next(
                (
                    it["partner_id"]
                    for it in invoice_data_raw
                    if it["invoice_key"] == invoice_key
                ),
                None,
            )
            if not partner_id:
                continue
            ordered_lines = []
            idx = 0
            total_product_lines = sum(
                len(by_key_pl[invoice_key].get(p.id, []))
                for p in productlinks_ordered
                if p.display_type == "product"
            )
            for pl in productlinks_ordered:
                if pl.display_type in ("line_section", "line_note"):
                    ordered_lines.append(
                        {
                            "display_type": pl.display_type,
                            "name": pl.line_name or "",
                            "_productlink": pl,
                        }
                    )
                else:
                    pl_items = by_key_pl[invoice_key].get(pl.id, [])
                    for item in pl_items:
                        idx += 1
                        item["_invoice_index"] = idx
                        item["_invoice_total"] = total_product_lines
                    ordered_lines.extend(pl_items)
            # Re-run template render with correct _invoice_index
            for item in ordered_lines:
                if item.get("_productlink") and item.get("billable_item_model"):
                    productlink = item["_productlink"]
                    if productlink.billable_item_detail_desc:
                        billable_item = self.env[item["billable_item_model"]].browse(
                            item.get("billable_item_res_id")
                        )
                        partner = self.env["res.partner"].browse(item["partner_id"])
                        product = self.env["product.product"].browse(
                            item.get("product_id")
                        )
                        ctx = self.env["product.category"].get_jinja2_template_context(
                            billable_item,
                            invoiceset=invoiceset,
                            productlink=productlink,
                            product=product,
                            partner=partner,
                            quantity=item.get("quantity", 0),
                            invoice_index=item.get("_invoice_index"),
                            groupvalue=item.get("_groupvalue", ""),
                        )
                        lang = partner.lang if partner else False
                        template_src = (
                            productlink.with_context(
                                lang=lang
                            ).billable_item_detail_desc
                            if lang
                            else productlink.billable_item_detail_desc
                        )
                        try:
                            name = Template(template_src).render(**ctx)
                            if name:
                                item["name"] = name
                        except TemplateError:
                            pass
            result.append(
                {
                    "invoice_key": invoice_key,
                    "partner_id": partner_id,
                    "lines": ordered_lines,
                }
            )
        return result

    # -------------------------------------------------------------------------
    # Invoice creation
    # -------------------------------------------------------------------------

    @api.model
    def create_invoice(self, invoiceset, invoice_data):
        if not self._pre_create_invoice(invoiceset, invoice_data):
            return None
        invoice = self._create_invoice(invoiceset, invoice_data)
        return self._post_create_invoice(invoiceset, invoice_data, invoice)

    @api.model
    def _pre_create_invoice(self, invoiceset, invoice_data):
        return True

    @api.model
    def _post_create_invoice(self, invoiceset, invoice_data, invoice):
        return invoice

    @api.model
    def _compute_invoice_total_from_data(self, invoice_data):
        """Approximate total from lines to decide invoice vs refund."""
        total = 0.0
        product_product = self.env["product.product"]
        for line in invoice_data.get("lines", []):
            if line.get("display_type") in ("line_section", "line_note"):
                continue
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = product_product.browse(product_id)
            qty = float(line.get("quantity", 0))
            total += qty * (product.lst_price or 0.0)
        return total

    @api.model
    def _get_move_type_for_invoice(self, invoiceset, invoice_data):
        """Return move_type: out_invoice, out_refund, in_invoice, or in_refund."""
        total = self._compute_invoice_total_from_data(invoice_data)
        if invoiceset.invoice_type == "customer":
            return "out_refund" if total < 0 else "out_invoice"
        return "in_refund" if total < 0 else "in_invoice"

    @api.model
    def _create_invoice(self, invoiceset, invoice_data):
        """Create a single account.move from one invoice_data dict.

        Kept for backward compatibility; the batch path in
        :meth:`_create_invoices_batch` is preferred for mass generation.
        """
        company = invoiceset.company_id or self.env.company
        vals = self._prepare_invoice_vals(invoiceset, invoice_data)
        return self.env["account.move"].with_company(company).create(vals)

    @api.model
    # pylint: disable=too-many-locals
    def _create_invoices_batch(self, invoiceset, invoice_data_list):
        """Create all draft invoices in one ``create([...])`` call.

        Returns the number of invoices effectively created. Honors the
        existing ``_pre_create_invoice`` / ``_post_create_invoice`` hooks
        (called once per record, just not interleaved with creation).
        """
        company = invoiceset.company_id or self.env.company
        # Filter through the pre-hook.
        kept = [d for d in invoice_data_list if self._pre_create_invoice(invoiceset, d)]
        if not kept:
            _logger.debug(
                "[invoiceset %s] _create_invoices_batch: empty chunk after pre-hook",
                invoiceset.alphanum_code or invoiceset.id,
            )
            return 0
        t0 = fields.Datetime.now()
        # Single ir.model.fields lookup per billable model, reused for
        # every line (was previously one search per line).
        m2o_cache = {}
        vals_list = [
            self._prepare_invoice_vals(invoiceset, d, m2o_cache=m2o_cache) for d in kept
        ]
        t_prepare = (fields.Datetime.now() - t0).total_seconds()
        move_model = (
            self.env["account.move"]
            .with_company(company)
            .with_context(**self._MASS_CREATE_CONTEXT)
        )
        t1 = fields.Datetime.now()
        moves = move_model.create(vals_list)
        t_create = (fields.Datetime.now() - t1).total_seconds()
        # Run the post-hook so existing overrides keep working.
        t2 = fields.Datetime.now()
        created = 0
        for data, move in zip(kept, moves):
            if self._post_create_invoice(invoiceset, data, move):
                created += 1
        t_post = (fields.Datetime.now() - t2).total_seconds()
        _logger.info(
            "[invoiceset %s] batch timings: prepare=%.2fs create=%.2fs "
            "post=%.2fs (%s moves)",
            invoiceset.alphanum_code or invoiceset.id,
            t_prepare,
            t_create,
            t_post,
            len(moves),
        )
        return created

    @api.model
    def _prepare_invoice_vals(  # pylint: disable=R0912,R0914
        self, invoiceset, invoice_data, m2o_cache=None
    ):
        """Build the ``vals`` dict for a single ``account.move`` create.
        ``m2o_cache`` is an optional dict reused across calls to avoid
        repeating the ``ir.model.fields`` lookup for the same billable
        model. When omitted a local one is used (single-shot mode).
        """
        if m2o_cache is None:
            m2o_cache = {}
        move_type = self._get_move_type_for_invoice(invoiceset, invoice_data)
        company = invoiceset.company_id or self.env.company
        vals = {
            "invoiceset_id": invoiceset.id,
            "partner_id": invoice_data["partner_id"],
            "invoice_date": invoiceset.invoice_date,
            "move_type": move_type,
            "state": "draft",
            "name": "/",
            "company_id": company.id,
        }
        if invoiceset.payment_term_id:
            vals["invoice_payment_term_id"] = invoiceset.payment_term_id.id
        elif invoiceset.invoice_date_due:
            vals["invoice_date_due"] = invoiceset.invoice_date_due
        if invoiceset.invoice_user_id:
            vals["invoice_user_id"] = invoiceset.invoice_user_id.id
        if invoiceset.journal_id:
            vals["journal_id"] = invoiceset.journal_id.id
        lines = []
        for line in invoice_data.get("lines", []):
            display_type = line.get("display_type")
            if display_type in ("line_section", "line_note"):
                line_vals = {
                    "display_type": display_type,
                    "name": line.get("name", ""),
                }
            else:
                line_vals = {
                    "product_id": line["product_id"],
                    "quantity": line["quantity"],
                    "billable_item_model": line["billable_item_model"],
                    "billable_item_res_id": line["billable_item_res_id"],
                }
                if line.get("name"):
                    line_vals["name"] = line["name"]
                productlink = line.get("_productlink")
                category = (
                    productlink.product_id.product_tmpl_id.categ_id
                    if productlink
                    and productlink.product_id
                    and productlink.product_id.product_tmpl_id
                    else None
                )
                if category:
                    if category.tax_ids:
                        line_vals["tax_ids"] = [(6, 0, category.tax_ids.ids)]
                    bi_model = line["billable_item_model"]
                    if bi_model not in m2o_cache:
                        m2o_cache[bi_model] = self._get_move_line_m2o_to_model(bi_model)
                    m2o_field = m2o_cache[bi_model]
                    if m2o_field and line.get("billable_item_res_id"):
                        line_vals[m2o_field] = line["billable_item_res_id"]
                    billable_item = self.env[bi_model].browse(
                        line.get("billable_item_res_id")
                    )
                    if billable_item.exists() and category.move_line_field_map_ids:
                        self._apply_move_line_field_mappings(
                            line_vals, billable_item, category.move_line_field_map_ids
                        )
            lines.append((0, 0, line_vals))
        if lines:
            vals["invoice_line_ids"] = lines

        if invoiceset.comment_template_ids:
            vals["comment_template_ids"] = [(6, 0, invoiceset.comment_template_ids.ids)]

        return vals

    @api.model
    def _get_move_line_m2o_to_model(self, model_name):
        """
        Return the field name of the first Many2one on account.move.line
        that points to the given model, or False if none exists.
        """
        if not model_name:
            return False
        field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "account.move.line"),
                ("relation", "=", model_name),
                ("ttype", "=", "many2one"),
            ],
            limit=1,
        )
        return field.name if field else False

    @api.model
    def _apply_move_line_field_mappings(
        self, line_vals, billable_item, map_ids
    ):  # pylint: disable=R0912
        """
        Apply field mappings: copy values from billable_item and/or default records
        to line_vals for account.move.line creation. Handles analytic_distribution
        conversion when billable has analytic_account_id (Many2one).
        """
        for map_rec in map_ids:
            ml_field = map_rec.move_line_field_id
            if not ml_field:
                continue
            ml_name = ml_field.name
            value = None

            if map_rec.value_source == "fixed":
                if map_rec._move_line_field_expects_record():
                    value = map_rec.default_record_ref
                else:
                    value = map_rec._parse_fixed_value(ml_field, map_rec.fixed_value)
            else:
                # from_billable or billable_or_fixed: try billable first
                bi_field = map_rec.billable_item_field_id
                if bi_field:
                    try:
                        value = getattr(billable_item, bi_field.name, None)
                    except (AttributeError, KeyError):
                        pass
                if (
                    value is None or value is False
                ) and map_rec.value_source == "billable_or_fixed":
                    if map_rec._move_line_field_expects_record():
                        value = map_rec.default_record_ref
                    else:
                        value = map_rec._parse_fixed_value(
                            ml_field, map_rec.fixed_value
                        )

            if value is None or value is False:
                continue
            # analytic_distribution: Many2one analytic_account_id → {str(id): 100.0}
            if ml_name == "analytic_distribution":
                if hasattr(value, "id") and value.id:
                    line_vals[ml_name] = {str(value.id): 100.0}
                continue
            # Many2one: use id
            if ml_field.ttype == "many2one":
                value = value.id if hasattr(value, "id") else value
            line_vals[ml_name] = value

    # -------------------------------------------------------------------------
    # Cancel
    # -------------------------------------------------------------------------

    def cancel_invoices(self):
        self.ensure_one()
        # If a background job is still alive (pending/enqueued/started or
        # already failed waiting for retry), cancel it first so it does not
        # recreate invoices right after we delete them.
        job = self.queue_job_id
        if job and job.state in ("pending", "enqueued", "started", "failed"):
            try:
                job.button_cancelled()
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "Could not cancel queue.job %s for invoiceset %s",
                    job.uuid,
                    self.id,
                )
        self.move_ids.with_context(cancelling_invoiceset=True).unlink()
        self.write(
            {
                "state": "configured",
                "calculation_started_at": False,
                "calculation_finished_at": False,
                "calculation_speed_inv_per_sec": 0.0,
                "invoice_generation_progress": 0.0,
                "last_calculation_error": False,
                "queue_job_id": False,
            }
        )


class AccountInvoicesetProductlink(models.Model):
    _name = "account.invoiceset.productlink"
    _description = "Invoice Set Product"
    _order = "sequence, id"

    DISPLAY_TYPE_SELECTION = [
        ("product", "Product"),
        ("line_section", "Section"),
        ("line_note", "Note"),
    ]

    max_size_productlink_code = 100

    sequence = fields.Integer(default=10)
    invoiceset_id = fields.Many2one(
        string="Invoice Set",
        comodel_name="account.invoiceset",
        index=True,
        ondelete="cascade",
    )
    display_type = fields.Selection(
        DISPLAY_TYPE_SELECTION,
        string="Line type",
        default="product",
        required=True,
    )
    line_name = fields.Char(
        string="Section / Note",
        help="Label for section or note. Shown in invoice lines when type is Section or"
        " Note.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        required=False,
        index=True,
        ondelete="restrict",
    )
    name = fields.Char(
        string="Identifier of productlink",
        size=max_size_productlink_code,
        store=True,
        index=True,
        compute="_compute_name",
    )
    categ_id = fields.Many2one(
        string="Category",
        comodel_name="product.category",
        store=True,
        compute="_compute_categ_id",
    )
    lst_price = fields.Float(
        string="Price",
        store=True,
        compute="_compute_lst_price",
    )
    populated = fields.Boolean(
        default=False,
        readonly=True,
    )

    billable_item_model_id = fields.Many2one(
        string="Billable-items Model",
        comodel_name="ir.model",
        store=True,
        compute="_compute_billable_item_model_id",
    )
    billable_item_quantity_field = fields.Char(
        string="Quantity Field",
        store=True,
        compute="_compute_billable_item_quantity_field",
    )
    billable_item_quantity_label = fields.Char(
        string="Label of the quantity field",
        related="product_id.product_tmpl_id.categ_id.billable_item_quantity_label",
    )
    billable_item_quantity_ratio = fields.Float(
        string="Quantity ratio",
        related="product_id.product_tmpl_id.categ_id.billable_item_quantity_ratio",
    )
    billable_item_group_field = fields.Char(
        string="Field for grouping",
        store=True,
        compute="_compute_billable_item_group_field",
        readonly=False,
    )
    billable_item_detail_desc = fields.Char(
        string="Template for invoice lines",
        related="product_id.product_tmpl_id.categ_id.billable_item_detail_desc",
    )
    billable_item_domain = fields.Char(
        string="Pre-filter on billable items",
        store=True,
        compute="_compute_billable_item_domain",
        readonly=False,
    )

    selectable_item_ids = fields.One2many(
        string="Selectable Records",
        comodel_name="account.selectable.item",
        inverse_name="productlink_id",
    )
    number_of_selectable_items = fields.Integer(
        string="Number of selectable records",
        compute="_compute_number_of_selectable_items",
    )
    selected_item_ids = fields.One2many(
        string="Selected Records",
        comodel_name="account.selectable.item",
        compute="_compute_selected_item_ids",
    )
    number_of_selected_items = fields.Integer(
        string="Number of selected records",
        store=True,
        compute="_compute_number_of_selected_items",
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE (name)", "Existing Product."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.display_type in ("line_section", "line_note"):
                rec.write({"populated": True})
        return records

    def write(self, vals):
        res = super().write(vals)
        if "display_type" in vals:
            for rec in self:
                if rec.display_type in ("line_section", "line_note"):
                    rec.write({"populated": True})
        return res

    @api.constrains("display_type", "product_id")
    def _check_product_required(self):
        for rec in self:
            if rec.display_type == "product" and not rec.product_id:
                raise ValidationError(
                    self.env._("Product is required for product lines.")
                )

    @api.constrains("invoiceset_id", "product_id", "display_type")
    def _check_product_unique_per_invoiceset(self):
        for rec in self:
            if rec.display_type != "product" or not rec.product_id:
                continue
            dup = self.search(
                [
                    ("invoiceset_id", "=", rec.invoiceset_id.id),
                    ("product_id", "=", rec.product_id.id),
                    ("display_type", "=", "product"),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if dup:
                raise ValidationError(
                    self.env._(
                        "The same product cannot appear more "
                        "than once in an invoice set."
                    )
                )

    @api.depends(
        "invoiceset_id",
        "invoiceset_id.alphanum_code",
        "product_id",
        "product_id.product_tmpl_id.name",
        "display_type",
        "sequence",
    )
    def _compute_name(self):
        default_lang = self.env.lang or "en_US"
        for record in self:
            name = ""
            if record.invoiceset_id:
                if record.display_type == "product" and record.product_id:
                    product_name = record.product_id.product_tmpl_id.with_context(
                        lang=default_lang
                    ).name
                    name = f"{record.invoiceset_id.alphanum_code}-{product_name}"
                elif record.display_type in ("line_section", "line_note"):
                    code = record.invoiceset_id.alphanum_code
                    dtype = record.display_type
                    seq = record.sequence
                    name = f"{code}-{dtype}-{seq}-{record.id or 0}"
            record.name = (name or f"pl-{record.id}")[: self.max_size_productlink_code]

    @api.depends("product_id")
    def _compute_categ_id(self):
        for record in self:
            record.categ_id = (
                record.product_id.product_tmpl_id.categ_id
                if record.product_id
                else False
            )

    @api.depends("product_id")
    def _compute_lst_price(self):
        for record in self:
            record.lst_price = record.product_id.lst_price if record.product_id else 0.0

    @api.depends("product_id")
    def _compute_billable_item_model_id(self):
        for record in self:
            category = (
                record.product_id.product_tmpl_id.categ_id
                if record.product_id
                else False
            )
            record.billable_item_model_id = (
                category.billable_item_model_id if category else False
            )

    @api.depends("product_id")
    def _compute_billable_item_quantity_field(self):
        for record in self:
            category = (
                record.product_id.product_tmpl_id.categ_id
                if record.product_id
                else False
            )
            qty_field = category.billable_item_quantity_field_id if category else False
            record.billable_item_quantity_field = qty_field.name if qty_field else False

    @api.depends(
        "product_id", "product_id.product_tmpl_id.categ_id.billable_item_group_field_id"
    )
    def _compute_billable_item_group_field(self):
        for record in self:
            category = (
                record.product_id.product_tmpl_id.categ_id
                if record.product_id
                else False
            )
            group_field_id = (
                category.billable_item_group_field_id if category else False
            )
            record.billable_item_group_field = (
                group_field_id.name if group_field_id else False
            )

    @api.depends("product_id")
    def _compute_billable_item_domain(self):
        for record in self:
            category = (
                record.product_id.product_tmpl_id.categ_id
                if record.product_id
                else False
            )
            record.billable_item_domain = (
                category.billable_item_domain if category else False
            )

    @api.depends("selectable_item_ids")
    def _compute_number_of_selectable_items(self):
        data = self.env["account.selectable.item"].read_group(
            [("productlink_id", "in", self.ids)],
            ["productlink_id"],
            ["productlink_id"],
        )
        mapped = {d["productlink_id"][0]: d["productlink_id_count"] for d in data}
        for record in self:
            record.number_of_selectable_items = mapped.get(record.id, 0)

    @api.depends("selectable_item_ids", "selectable_item_ids.selected")
    def _compute_selected_item_ids(self):
        for record in self:
            record.selected_item_ids = record.selectable_item_ids.filtered("selected")

    @api.depends("selectable_item_ids.selected")
    def _compute_number_of_selected_items(self):
        data = self.env["account.selectable.item"].read_group(
            [("productlink_id", "in", self.ids), ("selected", "=", True)],
            ["productlink_id"],
            ["productlink_id"],
        )
        mapped = {d["productlink_id"][0]: d["productlink_id_count"] for d in data}
        for record in self:
            record.number_of_selected_items = mapped.get(record.id, 0)

    def action_config_billable_item_fields(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"{self.env._('Product')} : {self.product_id.product_tmpl_id.name}",
            "res_model": "wizard.config.billable.item.fields",
            "view_mode": "form",
            "target": "new",
        }

    def action_show_selectable_items(self):
        self.ensure_one()
        if self.invoiceset_id.state == "draft" and not self.number_of_selectable_items:
            self.populate_selectable_items(self)
            self.update_populated()

        title_prefix = self.env._("Selectable Items. Product:")
        domain = [("productlink_id", "=", self.id)]
        if self.invoiceset_id.state not in ("draft", "configured"):
            title_prefix = self.env._("Selected Items. Product:")
            domain.append(("selected", "=", True))

        ctx = self._get_context_hide_fields(self.categ_id, self.invoiceset_id.state)
        ctx["create"] = False

        # Try hybrid view (shows billable model columns) or fallback to standard list
        hybrid = self.env[
            "account.selectable.item.hybrid.view"
        ]._get_or_create_for_category(self.categ_id)
        if hybrid and hybrid.model_id and hybrid.tree_view_id and hybrid.search_view_id:
            # Hybrid model uses x_productlink_id, x_selected
            # (x_ prefix for manual fields)
            hybrid_domain = [("x_productlink_id", "=", self.id)]
            if self.invoiceset_id.state not in ("draft", "configured"):
                hybrid_domain.append(("x_selected", "=", True))
            views = [(hybrid.tree_view_id.id, "list")]
            return {
                "type": "ir.actions.act_window",
                "name": f"{title_prefix} {self.product_id.product_tmpl_id.name}",
                "res_model": hybrid.model_name,
                "view_mode": "list",
                "views": views,
                "search_view_id": hybrid.search_view_id.id,
                "target": "current",
                "domain": hybrid_domain,
                "context": ctx,
            }

        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")
        ctx["selectable_items_categ_id"] = self.categ_id.id
        return {
            "type": "ir.actions.act_window",
            "name": f"{title_prefix} {self.product_id.product_tmpl_id.name}",
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": domain,
            "context": ctx,
        }

    @api.model
    def _get_context_hide_fields(self, category, current_state="draft"):
        context = {}
        if not category.billable_item_quantity_field_id:
            context["hide_quantity"] = True
        else:
            context["billable_item_quantity_label"] = (
                category.billable_item_quantity_label
            )
        if current_state not in ("draft", "configured"):
            context["hide_selectors"] = True
        return context

    def _confirm_action(self, message, operation):
        self.ensure_one()
        if self.invoiceset_id.state not in ("draft", "configured"):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Warning"),
                    "message": self.env._(
                        "This operation is only allowed when the invoice set is in the "
                        "'draft' or 'configured' state."
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": f"{self.env._('Product')} : {self.product_id.product_tmpl_id.name}",
            "res_model": "wizard.confirm.productlink.action",
            "view_mode": "form",
            "target": "new",
            "context": {"confirm_message": message, "operation": operation},
        }

    def action_refresh_selectable_items(self):
        self.ensure_one()
        return self._confirm_action(
            self.env._(
                "You are about to refresh the lines associated with this product. "
                "This will cause the current selection to be lost."
            ),
            "refresh_selectable_items",
        )

    def action_delete_selectable_items(self):
        self.ensure_one()
        return self._confirm_action(
            self.env._(
                "You are about to delete all lines associated with this product."
            ),
            "delete_selectable_items",
        )

    def action_delete_line(self):
        self.ensure_one()
        return self._confirm_action(
            self.env._(
                "You are about to remove this product from the invoice set. "
                "Therefore, its associated lines will also be deleted."
            ),
            "delete",
        )

    def refresh_selectable_items(self):
        self.delete_selectable_items()
        for record in self:
            record.populate_selectable_items(record)
        self.update_populated()

    def delete_selectable_items(self):
        selectable = self.env["account.selectable.item"]
        for record in self:
            selectable.search([("productlink_id", "=", record.id)]).unlink()
            record.update_populated()

    # -------------------------------------------------------------------------
    # SAFE population using ORM + safe_eval domain
    # -------------------------------------------------------------------------

    def populate_selectable_items(
        self, productlink
    ):  # pylint: disable=R0912,R0914,R0915
        product = productlink.product_id
        category = product.product_tmpl_id.categ_id
        if not category or not category.billable_item_model_id:
            _logger.info(
                "[base_invoicing] populate_selectable_items: skip - no category or "
                "billable_item_model_id (productlink_id=%s)",
                productlink.id,
            )
            return

        model_name = category.billable_item_model_id.sudo().model
        billable_model = self.env[model_name]

        partner_field = getattr(
            billable_model, "_billing_partner_id_name", "partner_id"
        )
        quantity_field = (
            category.billable_item_quantity_field_id.name
            if category.billable_item_quantity_field_id
            else None
        )

        domain = (
            [("active", "=", True)]
            if self.env["account.billable.item"].exists_active_field(model_name)
            else []
        )
        domain.append((partner_field, "!=", False))

        # Apply optional domain stored as python-domain string
        if productlink.billable_item_domain:
            try:
                extra_domain = safe_eval(productlink.billable_item_domain, {})
                if isinstance(extra_domain, list):
                    domain += extra_domain
                    _logger.info(
                        "[base_invoicing] populate_selectable_items: applied "
                        "billable_item_domain from productlink/category: %s",
                        productlink.billable_item_domain,
                    )
            except (ValueError, SyntaxError) as err:
                raise UserError(
                    self.env._("Invalid domain for billable items: %s") % str(err)
                ) from err
        else:
            _logger.info(
                "[base_invoicing] populate_selectable_items: no billable_item_domain "
                "on category (productlink_id=%s, categ_id=%s)",
                productlink.id,
                category.id,
            )

        if productlink.product_id.product_tmpl_id.link_with_billable_items:
            # Keep legacy behavior
            domain.append(("product_id", "=", productlink.product_id.id))
            _logger.info(
                "[base_invoicing] populate_selectable_items: added product_id=%s "
                "(link_with_billable_items=True)",
                productlink.product_id.id,
            )

        _logger.info(
            "[base_invoicing] populate_selectable_items: model=%s domain=%s "
            "productlink_id=%s categ_id=%s product=%s",
            model_name,
            domain,
            productlink.id,
            category.id,
            productlink.product_id.display_name,
        )

        fields_to_read = [partner_field]
        if quantity_field:
            fields_to_read.append(quantity_field)

        aux_map = self._get_aux_fields_map(category)
        fields_to_read += list(aux_map.values())

        # Avoid duplicates: delete existing selectable items first for this link
        selectable_model = self.env["account.selectable.item"]
        selectable_model.search([("productlink_id", "=", productlink.id)]).unlink()

        items = billable_model.search(domain)
        count = len(items)
        _logger.info(
            "[base_invoicing] populate_selectable_items: search returned %d records "
            "for model=%s (productlink_id=%s)",
            count,
            model_name,
            productlink.id,
        )
        if not items:
            return

        rows = items.read(fields_to_read)

        create_vals = []
        for row in rows:
            partner_val = row.get(partner_field)
            partner_id = (
                partner_val[0]
                if isinstance(partner_val, (list, tuple)) and partner_val
                else partner_val
            )
            if not partner_id:
                continue

            qty = 1.0
            if quantity_field:
                qty = float(row.get(quantity_field) or 0.0)
            ratio = category.billable_item_quantity_ratio or 1.0
            if ratio != 1.0:
                qty *= ratio

            vals = {
                "productlink_id": productlink.id,
                "billable_item_model": model_name,
                "billable_item_res_id": row["id"],
                "partner_id": partner_id,
                "quantity": qty,
                "selected": True,
            }

            for dest, src in aux_map.items():
                raw = row.get(src)
                vals[dest] = self._aux_value_to_str(raw)

            create_vals.append(vals)

        if create_vals:
            selectable_model.create(create_vals)

    @api.model
    def _aux_value_to_str(self, value):
        """Convert raw field value to string for aux Char slots."""
        if value in (False, None):
            return ""
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return str(value[1])  # many2one (id, name)
        return str(value)

    @api.model
    def _get_aux_fields_map(self, category):
        """Return mapping {dest_field_on_selectable: src_field_on_billable}."""
        mapping = {}
        for idx, line in enumerate(
            category.aux_field_ids.sorted("sequence")[:20], start=1
        ):
            if line.field_id:
                mapping[f"aux_{idx:02d}"] = line.field_id.name
        return mapping

    def update_populated(self):
        self.ensure_one()
        data = self.env["account.selectable.item"].read_group(
            [("productlink_id", "=", self.id), ("selected", "=", True)],
            ["productlink_id"],
            ["productlink_id"],
        )
        count = data[0]["productlink_id_count"] if data else 0
        self.write({"populated": bool(count)})
