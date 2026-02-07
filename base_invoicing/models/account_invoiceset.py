# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=unused-argument
# pylint: disable=protected-access
# pylint: disable=duplicate-code
# pylint: disable=no-raise-unlink
# pylint: disable=translation-not-lazy
# pylint: disable=translation-positional-used
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=except-pass

import logging
import threading
from collections import defaultdict
from datetime import timedelta

from jinja2 import Template, TemplateError
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.sql import SQL

_logger = logging.getLogger(__name__)


class AccountInvoiceset(models.Model):
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
        string="Journal",
        comodel_name="account.journal",
        tracking=True,
    )
    payment_term_id = fields.Many2one(
        string="Payment Term",
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

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("configured", "Configured"),
            ("calculating", "In progress"),
            ("calculated", "Calculated"),
            ("committed", "Committed"),
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
        States 'calculating', 'calculated', 'committed' set by write() are preserved.
        """
        for record in self:
            state = record.state
            if state == "draft" and record.all_productlinks_configured:
                state = "configured"
            elif state == "configured" and not record.all_productlinks_configured:
                state = "draft"
            elif state == "calculated" and record.some_posted_invoice:
                state = "committed"
            elif state == "committed" and not record.some_posted_invoice:
                state = "calculated"
            # Do not overwrite 'calculating' or explicit calculated/committed
            record.state = state

    def _inverse_state(self):
        """Allow direct writes to state (e.g. calculating, calculated)."""
        # ORM persists the value when inverse exists; no extra logic needed
        pass

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

    @api.depends("productlink_ids", "productlink_ids.selectable_item_ids")
    def _compute_selectable_item_count(self):
        for record in self:
            record.selectable_item_count = self.env["account.selectable.item"].search_count(
                [("productlink_id.invoiceset_id", "=", record.id)]
            )

    @api.depends("productlink_ids", "productlink_ids.populated")
    def _compute_all_productlinks_configured(self):
        for record in self:
            record.all_productlinks_configured = bool(record.productlink_ids) and all(
                pl.populated for pl in record.productlink_ids
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
        invoicesets = super().create(vals_list)
        self.env["account.invoiceset.progress"].create(
            [{"invoiceset_id": inv.id} for inv in invoicesets]
        )
        return invoicesets

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
        self.env["account.invoiceset.progress"].search(
            [("invoiceset_id", "in", self.ids)]
        ).unlink()
        return super().unlink()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_show_invoices(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [("invoiceset_id", "=", self.id)],
            "context": {"default_move_type": "out_invoice"},
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
        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")
        ctx = {"create": False}
        first_pl = self.productlink_ids[:1]
        if first_pl.categ_id:
            ctx["selectable_items_categ_id"] = first_pl.categ_id.id
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Selectable Items"),
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": [("productlink_id.invoiceset_id", "=", self.id)],
            "context": ctx,
        }

    def action_show_invoices_pending_validation(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
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
            "context": {"default_move_type": "out_invoice"},
        }

    def action_show_invoices_posted(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
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
            "context": {"default_move_type": "out_invoice"},
        }

    def action_show_invoices_cancelled(self):
        self.ensure_one()
        tree_view = self.env.ref("base_invoicing.view_out_invoice_tree")
        form_view = self.env.ref("base_invoicing.view_move_form")
        search_view = self.env.ref("base_invoicing.view_account_invoice_filter")
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
            "context": {"default_move_type": "out_invoice"},
        }

    # -------------------------------------------------------------------------
    # Calculation entrypoints
    # -------------------------------------------------------------------------

    def calculate_invoiceset(self):
        self.ensure_one()

        if self.search_count([("state", "=", "calculating")]):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Warning"),
                    "message": self.env._(
                        "It is not possible to start the "
                        "calculation of this invoice set, "
                        "as another invoice set is currently "
                        "being processed. You must wait "
                        "until it finishes or interrupt it."
                    ),
                    "type": "warning",
                    "sticky": True,
                    "next": False,
                },
            }

        if self.state != "configured":
            return None

        # Clean non-selected selectable items for this invoiceset (Odoo 18: use SQL())
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

        run_background = bool(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("base_invoicing.mass_invoicing_run_background", False)
        )
        self.calculation_process(self.id, background=run_background)
        return None

    @api.model
    def calculate_all_configured_invoiceset(self):
        if self.search_count([("state", "=", "calculating")]):
            return
        for invoiceset in self.search([("state", "=", "configured")]):
            self.calculation_process(invoiceset.id, from_cron=True)

    # -------------------------------------------------------------------------
    # Background execution (kept for compatibility, made safer)
    # -------------------------------------------------------------------------

    @api.model
    def calculation_process(self, invoiceset_id, background=False, from_cron=False):
        invoiceset = self.browse(invoiceset_id)
        if not invoiceset.exists():
            return None

        if background:
            registry = self.env.registry
            uid = self.env.uid
            ctx = dict(self.env.context)

            def _run():
                # New cursor per thread (Odoo 18: Environment.manage was removed)
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, ctx)
                    env["account.invoiceset"]._invoice_generation_thread(invoiceset_id)

            threading.Thread(target=_run, daemon=True).start()
            return None

        return self.invoice_generation(invoiceset_id, from_cron=from_cron)

    @api.model
    def _invoice_generation_thread(self, invoiceset_id):
        # In thread we are already inside a dedicated cursor/env.
        self.invoice_generation(invoiceset_id, background=True)
        # Cursor closing/commit is managed by the context manager.

    # -------------------------------------------------------------------------
    # Core generation
    # -------------------------------------------------------------------------

    @api.model
    def invoice_generation(self, invoiceset_id, background=False, from_cron=False):
        invoiceset = self.browse(invoiceset_id)
        if not invoiceset.exists() or invoiceset.state != "configured":
            return None

        number_of_invoices = 0
        cancelled = False

        # Reset progress for background runs
        if background:
            invoiceset.write({"invoice_generation_progress": 0.0})
            self.env["account.invoiceset.progress"].sudo().search(
                [("invoiceset_id", "=", invoiceset.id)],
                limit=1,
            ).write({"invoice_generation_progress": 0.0, "stop_order": False})

        started_at = fields.Datetime.now()
        invoiceset.write({
            "state": "calculating",
            "calculation_started_at": started_at,
            "calculation_finished_at": False,
            "calculation_speed_inv_per_sec": 0.0,
        })
        suffix = (
            self.env._("(background)") if background else self.env._("(foreground)")
        )
        invoiceset.message_post(
            body=self.env._("Calculation Process: start") + " " + suffix
        )

        try:
            invoice_data = self.get_invoice_data(invoiceset)
            if not invoice_data:
                cancelled = True
            else:
                total_invoices = len(invoice_data)
                progress_model = self.env["account.invoiceset.progress"].sudo()
                progress_row = (
                    progress_model.search(
                        [("invoiceset_id", "=", invoiceset.id)], limit=1
                    )
                    if background
                    else None
                )
                # Batch size: commit/update progress every N invoices (avoids 1 commit per invoice)
                company = self.env.company
                progress_batch_size = max(
                    1,
                    int(company.mass_invoicing_progress_batch_size or 50),
                )

                for idx, inv_data in enumerate(invoice_data):
                    invoice = self.create_invoice(invoiceset, inv_data)
                    if invoice:
                        number_of_invoices += 1

                    if background and progress_row:
                        do_batch = (idx + 1) % progress_batch_size == 0 or (
                            idx + 1
                        ) == total_invoices
                        if do_batch:
                            progress_row.invalidate_recordset()
                            progress_row = progress_model.search(
                                [("invoiceset_id", "=", invoiceset.id)], limit=1
                            )
                            if progress_row.stop_order:
                                invoiceset.cancel_invoices()
                                cancelled = True
                                number_of_invoices = 0
                                break

                            progress = 100.0 * (idx + 1) / total_invoices
                            progress_row.write(
                                {"invoice_generation_progress": progress}
                            )
                            invoiceset.with_context(
                                tracking_disable=True
                            ).write({"invoice_generation_progress": progress})
                            self.env.cr.commit()

            finished_at = fields.Datetime.now()
            duration_sec = (finished_at - started_at).total_seconds()
            speed = (
                number_of_invoices / duration_sec
                if duration_sec and duration_sec > 0
                else 0.0
            )
            invoiceset.write({
                "state": "configured" if cancelled else "calculated",
                "calculation_finished_at": finished_at,
                "calculation_speed_inv_per_sec": round(speed, 2),
            })
            end_suffix = (
                self.env._("Cancelled")
                if cancelled
                else (self.env._("No. of invoices:") + f" {number_of_invoices}")
            )
            invoiceset.message_post(
                body=self.env._("Calculation Process: end.") + " " + end_suffix
            )

            if background:
                # Reset progress bar for next run
                invoiceset.write({"invoice_generation_progress": 0.0})
                self.env["account.invoiceset.progress"].sudo().search(
                    [("invoiceset_id", "=", invoiceset.id)],
                    limit=1,
                ).write({"invoice_generation_progress": 0.0, "stop_order": False})

        except (UserError, ValueError, TemplateError) as err:
            invoiceset.write({
                "state": "configured",
                "calculation_started_at": False,
                "calculation_finished_at": False,
                "calculation_speed_inv_per_sec": 0.0,
            })
            invoiceset.message_post(
                body=self.env._("Calculation Process: ERROR...") + " " + str(err)
            )

            raise

        return None

    # -------------------------------------------------------------------------
    # Invoice data extraction (no runtime class mutation)
    # -------------------------------------------------------------------------

    @api.model
    def get_invoice_data(self, invoiceset):
        if not self._pre_get_invoice_data(invoiceset):
            return None
        invoice_data = self._get_invoice_data(invoiceset)
        return self._post_get_invoice_data(invoiceset, invoice_data)

    @api.model
    def _pre_get_invoice_data(self, invoiceset):
        return True

    @api.model
    def _post_get_invoice_data(self, invoiceset, invoice_data):
        return invoice_data

    @api.model
    def _get_invoice_data(self, invoiceset):
        invoice_data_raw = []

        for productlink in invoiceset.productlink_ids:
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

                if not partner_id or quantity <= 0:
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
                }

                if productlink.billable_item_detail_desc:
                    lang = partner.lang if partner else False
                    template_src = (
                        productlink.with_context(lang=lang).billable_item_detail_desc
                        if lang
                        else productlink.billable_item_detail_desc
                    )
                    try:
                        name = Template(template_src).render(
                            billable_item=billable_item
                        )
                        if name:
                            vals["name"] = name
                    except TemplateError:
                        # Keep legacy behavior: ignore template errors
                        pass

                invoice_data_raw.append(vals)

        if not invoice_data_raw:
            return []

        grouped = defaultdict(list)
        for item in invoice_data_raw:
            grouped[item["invoice_key"]].append(item)

        return [
            {"invoice_key": key, "partner_id": lines[0]["partner_id"], "lines": lines}
            for key, lines in grouped.items()
        ]

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
    def _create_invoice(self, invoiceset, invoice_data):
        vals = {
            "invoiceset_id": invoiceset.id,
            "partner_id": invoice_data["partner_id"],
            "invoice_date": invoiceset.invoice_date,
            "move_type": "out_invoice",
            "state": "draft",
            "name": "/",
            "company_id": self.env.user.company_id.id,
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
            line_vals = {
                "product_id": line["product_id"],
                "quantity": line["quantity"],
                "billable_item_model": line["billable_item_model"],
                "billable_item_res_id": line["billable_item_res_id"],
            }
            if line.get("name"):
                line_vals["name"] = line["name"]
            # If account.move.line has a Many2one to the billable model, fill it
            m2o_field = self._get_move_line_m2o_to_model(line["billable_item_model"])
            if m2o_field and line.get("billable_item_res_id"):
                line_vals[m2o_field] = line["billable_item_res_id"]
            lines.append((0, 0, line_vals))
        if lines:
            vals["invoice_line_ids"] = lines

        if invoiceset.comment_template_ids:
            vals["comment_template_ids"] = [(6, 0, invoiceset.comment_template_ids.ids)]

        return self.env["account.move"].create(vals)

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

    # -------------------------------------------------------------------------
    # Stop/cancel helpers
    # -------------------------------------------------------------------------

    def stop_calculation(self):
        self.ensure_one()
        self.env["account.invoiceset.progress"].sudo().search(
            [("invoiceset_id", "=", self.id)],
            limit=1,
        ).write({"stop_order": True})

    @api.model
    def background_calculation_active(self, invoiceset_id):
        invoiceset = self.sudo().browse(invoiceset_id)
        if not invoiceset.exists() or invoiceset.state != "calculating":
            return False
        # Reset stale "calculating" (e.g. process died or server restarted)
        if self._is_calculation_stale(invoiceset):
            invoiceset.cancel_invoices()
            return False
        return bool(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("base_invoicing.mass_invoicing_run_background", False)
        )

    def _is_calculation_stale(self, invoiceset, max_age_minutes=10):
        """True if state is 'calculating' but no process is actually running."""
        if invoiceset.state != "calculating":
            return False
        started = invoiceset.calculation_started_at
        if not started:
            return True  # Legacy record without timestamp
        limit = fields.Datetime.now() - timedelta(minutes=max_age_minutes)
        return started < limit

    @api.model
    def cron_reset_stale_calculating_invoicesets(self, max_age_minutes=10):
        """Reset invoice sets stuck in 'calculating' (e.g. after process crash)."""
        stale = self.search([("state", "=", "calculating")]).filtered(
            lambda r: self._is_calculation_stale(r, max_age_minutes=max_age_minutes)
        )
        if stale:
            stale.cancel_invoices()

    def cancel_invoices(self):
        self.ensure_one()
        self.move_ids.unlink()
        self.write({
            "state": "configured",
            "calculation_started_at": False,
            "calculation_finished_at": False,
            "calculation_speed_inv_per_sec": 0.0,
        })

    @api.model
    def action_refresh_all_invoicesets_in_calculation_process(self):
        invoicesets = self.search([("state", "=", "calculating")])
        if not invoicesets:
            return None
        invoicesets.cancel_invoices()
        return {"type": "ir.actions.client", "tag": "reload"}


class AccountInvoicesetProductlink(models.Model):
    _name = "account.invoiceset.productlink"
    _description = "Invoice Set Product"

    max_size_productlink_code = 100

    invoiceset_id = fields.Many2one(
        string="Invoice Set",
        comodel_name="account.invoiceset",
        index=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        string="Product",
        comodel_name="product.product",
        required=True,
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
        compute="_compute_number_of_selected_items",
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE (name)", "Existing Product."),
    ]

    @api.depends(
        "invoiceset_id",
        "invoiceset_id.alphanum_code",
        "product_id",
        "product_id.product_tmpl_id.name",
    )
    def _compute_name(self):
        default_lang = self.env.lang or "en_US"
        for record in self:
            name = ""
            if record.invoiceset_id and record.product_id:
                product_name = record.product_id.product_tmpl_id.with_context(
                    lang=default_lang
                ).name
                name = f"{record.invoiceset_id.alphanum_code}-{product_name}"
            record.name = (name or "")[: self.max_size_productlink_code]

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
            record.billable_item_quantity_field = (
                qty_field.name if qty_field else False
            )

    @api.depends("product_id", "product_id.product_tmpl_id.categ_id.billable_item_group_field_id")
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

    @api.depends("selected_item_ids")
    def _compute_number_of_selected_items(self):
        for record in self:
            record.number_of_selected_items = len(record.selected_item_ids)

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
        hybrid = self.env["account.selectable.item.hybrid.view"]._get_or_create_for_category(
            self.categ_id
        )
        if hybrid and hybrid.model_id and hybrid.tree_view_id and hybrid.search_view_id:
            # Hybrid model uses x_productlink_id, x_selected (x_ prefix for manual fields)
            hybrid_domain = [("x_productlink_id", "=", self.id)]
            if self.invoiceset_id.state not in ("draft", "configured"):
                hybrid_domain.append(("x_selected", "=", True))
            return {
                "type": "ir.actions.act_window",
                "name": f"{title_prefix} {self.product_id.product_tmpl_id.name}",
                "res_model": hybrid.model_name,
                "view_mode": "list",
                "views": [(hybrid.tree_view_id.id, "list")],
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

    def populate_selectable_items(self, productlink):
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


class AccountInvoicesetProgress(models.Model):
    _name = "account.invoiceset.progress"
    _description = "Invoice set calculation progress"

    invoiceset_id = fields.Many2one(
        string="Invoice Set",
        comodel_name="account.invoiceset",
        index=True,
        readonly=True,
    )
    invoice_generation_progress = fields.Float(
        string="Percentage of progress during invoice generation",
        default=0.0,
        readonly=True,
    )
    stop_order = fields.Boolean(
        string="Active stop order",
        default=False,
    )
