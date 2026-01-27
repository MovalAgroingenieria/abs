# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import time
from collections import defaultdict

from jinja2 import Template, TemplateError
from psycopg2 import Error as PsycopgError
from psycopg2 import sql

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountInvoiceset(models.Model):
    _name = "account.invoiceset"
    _description = "Invoice Set"
    _inherit = ["simple.model", "mail.thread", "comment.template"]
    _order = "alphanum_code desc"
    _rec_name = "alphanum_code"

    _set_num_code = False
    _sequence_for_codes = "base_invoicing.mass_invoicing_seq_invoiceset_code_id"
    _size_name = 20
    _minlength = 0
    _maxlength = 20
    _allowed_blanks_in_code = False
    _set_alphanum_code_to_lowercase = False
    _set_alphanum_code_to_uppercase = True
    _size_description = 100

    alphanum_code = fields.Char(string="Code of invoice set", required=True)
    description = fields.Char(
        string="Description of invoice set",
        required=True,
        translate=True,
    )
    invoice_date = fields.Date(
        string="Invoicing Date",
        default=lambda self: fields.Date.context_today(self),
        required=True,
        index=True,
    )
    invoice_date_due = fields.Date(string="Due Date")
    journal_id = fields.Many2one(string="Journal", comodel_name="account.journal")
    payment_term_id = fields.Many2one(
        string="Payment Term", comodel_name="account.payment.term"
    )
    invoice_user_id = fields.Many2one(
        string="Sales Person",
        comodel_name="res.users",
        default=lambda self: self.env.user,
        required=True,
    )

    state = fields.Selection(
        string="State",
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
        index=True,
        tracking=True,
    )

    move_ids = fields.One2many(
        string="Invoices",
        comodel_name="account.move",
        inverse_name="invoiceset_id",
    )
    number_of_invoices = fields.Integer(
        string="Number of invoices",
        store=True,
        compute="_compute_number_of_invoices",
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
        string="Invoice generation progress (%)",
        default=0.0,
        compute="_compute_invoice_generation_progress",
    )
    calculated = fields.Boolean(
        string="Calculated",
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
    )

    # ---------------------------- display name ----------------------------

    def _compute_display_name(self):
        """Compute display_name without using deprecated name_get()."""
        for record in self:
            name = record.alphanum_code or ""
            if record.description:
                name = f"{name} ({record.description})"
            record.display_name = name

    # ------------------------------- computes -----------------------------

    @api.depends("all_productlinks_configured", "some_posted_invoice")
    def _compute_state(self):
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
            record.state = state

    @api.depends("move_ids")
    def _compute_number_of_invoices(self):
        for record in self:
            record.number_of_invoices = len(record.move_ids)

    @api.depends("productlink_ids", "productlink_ids.populated")
    def _compute_all_productlinks_configured(self):
        for record in self:
            record.all_productlinks_configured = bool(record.productlink_ids) and all(
                productlink.populated for productlink in record.productlink_ids
            )

    def _compute_invoice_generation_progress(self):
        progress_model = self.env["account.invoiceset.progress"].sudo()
        for record in self:
            progress = progress_model.search([("invoiceset_id", "=", record.id)], limit=1)
            record.invoice_generation_progress = progress.invoice_generation_progress or 0.0

    @api.depends("move_ids", "move_ids.state")
    def _compute_some_posted_invoice(self):
        for record in self:
            record.some_posted_invoice = any(move.state == "posted" for move in record.move_ids)

    # ------------------------------ lifecycle -----------------------------

    @api.model_create_multi
    def create(self, vals_list):
        invoicesets = super().create(vals_list)
        self.env["account.invoiceset.progress"].create(
            [{"invoiceset_id": inv.id} for inv in invoicesets]
        )
        return invoicesets

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "configured"):
                raise UserError(
                    self.env._(
                        "It is not possible to delete a calculated invoice set, "
                        "you must cancel it first."
                    )
                )
        self.env["account.invoiceset.progress"].search(
            [("invoiceset_id", "in", self.ids)]
        ).unlink()
        return super().unlink()

    # ------------------------------- actions ------------------------------

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

    # --------------------------- calculation flow -------------------------

    def calculate_invoiceset(self):
        self.ensure_one()

        if self.search_count([("state", "=", "calculating")]):
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Warning"),
                    "message": self.env._(
                        "It is not possible to start the calculation of this invoice set, "
                        "as another invoice set is currently being processed. You must wait "
                        "until it finishes or interrupt it."
                    ),
                    "type": "warning",
                    "sticky": True,
                    "next": False,
                },
            }

        if self.state != "configured":
            return None

        self.env.cr.execute(
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
            (self.id,),
        )

        run_background = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("base_invoicing.mass_invoicing_run_background", False)
        )
        self.calculation_process(self.id, background=bool(run_background))
        return None

    @api.model
    def calculate_all_configured_invoiceset(self):
        if self.search_count([("state", "=", "calculating")]):
            return
        for invoiceset in self.search([("state", "=", "configured")]):
            self.calculation_process(invoiceset.id, from_cron=True)

    @api.model
    def calculation_process(self, invoiceset_id, background=False, from_cron=False):
        invoiceset = self.browse(invoiceset_id)
        if not invoiceset.exists():
            return None

        if background:
            # Background execution must use a dedicated cursor + Environment.
            self._run_invoice_generation_in_thread(invoiceset.id)
            return None

        return self.invoice_generation(invoiceset_id, from_cron=from_cron)

    @api.model
    def _run_invoice_generation_in_thread(self, invoiceset_id):
        """Run invoice generation in background using a safe env/cursor."""
        import threading  # pylint: disable=import-outside-toplevel

        def _target(dbname, uid, ctx, invset_id):
            registry = self.env.registry
            with api.Environment.manage():
                cr = registry.cursor()
                try:
                    env = api.Environment(cr, uid, ctx)
                    env["account.invoiceset"].invoice_generation(invset_id, background=True)
                    cr.commit()
                except (UserError, PsycopgError) as err:
                    cr.rollback()
                    # Best-effort logging in chatter if possible
                    try:
                        env = api.Environment(cr, uid, ctx)
                        invset = env["account.invoiceset"].browse(invset_id)
                        if invset.exists():
                            invset.message_post(body=env._("Calculation Process: ERROR... %s") % str(err))
                            invset.write({"state": "configured"})
                            cr.commit()
                    except PsycopgError:
                        cr.rollback()
                finally:
                    cr.close()

        ctx = dict(self.env.context)
        th = threading.Thread(
            target=_target,
            args=(self.env.cr.dbname, self.env.uid, ctx, invoiceset_id),
            daemon=True,
        )
        th.start()

    @api.model
    def invoice_generation(self, invoiceset_id, background=False, from_cron=False):
        invoiceset = self.browse(invoiceset_id)
        if not invoiceset.exists() or invoiceset.state != "configured":
            return None

        tmp_cr = None
        number_of_invoices = 0

        try:
            invoiceset.write({"state": "calculating"})

            suffix = self.env._("(background)") if background else self.env._("(foreground)")

            if background:
                tmp_cr = self.env.registry.cursor()
                tmp_env = api.Environment(tmp_cr, self.env.uid, dict(self.env.context))
                tmp_env["account.invoiceset.progress"].sudo().search(
                    [("invoiceset_id", "=", invoiceset_id)], limit=1
                ).write({"invoice_generation_progress": 0.0, "stop_order": False})
                tmp_cr.commit()

            invoiceset.message_post(body=self.env._("Calculation Process: start") + " " + suffix)

            cancelled = False
            invoice_data = self.get_invoice_data(invoiceset)
            if not invoice_data:
                cancelled = True
            else:
                progress = 0.0
                step = 100.0 / len(invoice_data)

                for inv_data in invoice_data:
                    invoice = self.create_invoice(invoiceset, inv_data)
                    if invoice:
                        number_of_invoices += 1

                    if background and tmp_cr:
                        tmp_env = api.Environment(tmp_cr, self.env.uid, dict(self.env.context))
                        prog = tmp_env["account.invoiceset.progress"].sudo().search(
                            [("invoiceset_id", "=", invoiceset_id)], limit=1
                        )
                        tmp_cr.commit()

                        if prog.stop_order:
                            invoiceset.cancel_invoices()
                            cancelled = True
                            number_of_invoices = 0
                            break

                        progress += step
                        prog.write({"invoice_generation_progress": progress})
                        tmp_cr.commit()

            time.sleep(1)
            invoiceset.write({"state": "configured" if cancelled else "calculated"})

            end_suffix = (
                self.env._("Cancelled")
                if cancelled
                else (self.env._("No. of invoices:") + f" {number_of_invoices}")
            )
            invoiceset.message_post(body=self.env._("Calculation Process: end.") + " " + end_suffix)

            if background and tmp_cr:
                tmp_env = api.Environment(tmp_cr, self.env.uid, dict(self.env.context))
                tmp_env["account.invoiceset.progress"].sudo().search(
                    [("invoiceset_id", "=", invoiceset_id)], limit=1
                ).write({"invoice_generation_progress": 0.0, "stop_order": False})
                tmp_cr.commit()

        except (UserError, TemplateError, PsycopgError) as err:
            invoiceset.write({"state": "configured"})
            invoiceset.message_post(body=self.env._("Calculation Process: ERROR...") + " " + str(err))
            if background:
                # In background, avoid raising to the RPC layer
                if tmp_cr:
                    tmp_cr.rollback()
            else:
                raise UserError(str(err)) from err
        finally:
            if tmp_cr:
                tmp_cr.close()

        return None

    # ---------------------------- invoice data ----------------------------

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
        billable_item_helper = self.env["account.billable.item"]

        for productlink in invoiceset.productlink_ids:
            if not productlink.billable_item_model_id:
                continue

            model_name = productlink.sudo().billable_item_model_id.model
            quantity_field = productlink.billable_item_quantity_field
            group_field = productlink.billable_item_group_field

            model_billable = self.env[model_name]
            inherits_billable = billable_item_helper.inherits_from_account_billable_item(model_name)

            for selected_item in productlink.selected_item_ids:
                billable_item = model_billable.browse(selected_item.billable_item_res_id)
                if not billable_item.exists():
                    continue

                # Do NOT mutate class attributes in runtime (multiworker unsafe).
                if inherits_billable:
                    partner_field = getattr(model_billable, "_billing_partner_id_name", "partner_id")
                    partner = getattr(billable_item, partner_field, False)
                    partner_id = partner.id if partner else False
                    quantity = getattr(billable_item, quantity_field, 0.0) if quantity_field else 1.0
                    groupvalue = str(getattr(billable_item, group_field, "")) if group_field else ""
                else:
                    partner_id = billable_item.partner_id.id if getattr(billable_item, "partner_id", False) else False
                    quantity = getattr(billable_item, quantity_field, 0.0) if quantity_field else 0.0
                    groupvalue = str(getattr(billable_item, group_field, "")) if group_field else ""

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
                    lang = getattr(getattr(billable_item, "partner_id", False), "lang", False)
                    template_src = productlink.billable_item_detail_desc
                    if lang:
                        template_src = productlink.with_context(lang=lang).billable_item_detail_desc
                    try:
                        rendered = Template(template_src).render(billable_item=billable_item)
                        if rendered:
                            vals["name"] = rendered
                    except TemplateError:
                        # Ignore invalid templates, keep default description.
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

    # ---------------------------- invoice create --------------------------

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
            lines.append((0, 0, line_vals))
        if lines:
            vals["invoice_line_ids"] = lines

        if invoiceset.comment_template_ids:
            vals["comment_template_ids"] = [(6, 0, invoiceset.comment_template_ids.ids)]

        return self.env["account.move"].create(vals)

    # ------------------------------ stop/cancel ----------------------------

    def stop_calculation(self):
        self.ensure_one()
        self.env.cr.execute(
            """
            UPDATE account_invoiceset_progress
               SET stop_order = TRUE
             WHERE invoiceset_id = %s
            """,
            (self.id,),
        )

    @api.model
    def background_calculation_active(self, invoiceset_id):
        invoiceset = self.sudo().browse(invoiceset_id)
        if not invoiceset.exists() or invoiceset.state != "calculating":
            return False
        return bool(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("base_invoicing.mass_invoicing_run_background", False)
        )

    def cancel_invoices(self):
        self.ensure_one()
        self.move_ids.unlink()
        self.write({"state": "configured"})

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
    lst_price = fields.Float(string="Price", store=True, compute="_compute_lst_price")
    populated = fields.Boolean(string="Populated", default=False, readonly=True)

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
                product_name = record.product_id.product_tmpl_id.with_context(lang=default_lang).name
                name = f"{record.invoiceset_id.alphanum_code}-{product_name}"
            record.name = name[: record.max_size_productlink_code]

    @api.depends("product_id")
    def _compute_categ_id(self):
        for record in self:
            record.categ_id = record.product_id.product_tmpl_id.categ_id if record.product_id else False

    @api.depends("product_id")
    def _compute_lst_price(self):
        for record in self:
            record.lst_price = record.product_id.lst_price if record.product_id else 0.0

    @api.depends("product_id")
    def _compute_billable_item_model_id(self):
        for record in self:
            category = record.product_id.product_tmpl_id.categ_id if record.product_id else False
            record.billable_item_model_id = category.billable_item_model_id if category else False

    @api.depends("product_id")
    def _compute_billable_item_quantity_field(self):
        for record in self:
            category = record.product_id.product_tmpl_id.categ_id if record.product_id else False
            record.billable_item_quantity_field = category.billable_item_quantity_field if category else False

    @api.depends("product_id")
    def _compute_billable_item_group_field(self):
        for record in self:
            category = record.product_id.product_tmpl_id.categ_id if record.product_id else False
            record.billable_item_group_field = category.billable_item_group_field if category else False

    @api.depends("product_id")
    def _compute_billable_item_domain(self):
        for record in self:
            category = record.product_id.product_tmpl_id.categ_id if record.product_id else False
            record.billable_item_domain = category.billable_item_domain if category else False

    @api.depends("selectable_item_ids")
    def _compute_number_of_selectable_items(self):
        for record in self:
            record.number_of_selectable_items = len(record.selectable_item_ids)

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

        tree_view = self.env.ref("base_invoicing.account_selectable_item_view_tree")
        search_view = self.env.ref("base_invoicing.account_selectable_item_view_search")

        title_prefix = self.env._("Selectable Items. Product:")
        domain = [("productlink_id", "=", self.id)]
        if self.invoiceset_id.state not in ("draft", "configured"):
            title_prefix = self.env._("Selected Items. Product:")
            domain.append(("selected", "=", True))

        return {
            "type": "ir.actions.act_window",
            "name": f"{title_prefix} {self.product_id.product_tmpl_id.name}",
            "res_model": "account.selectable.item",
            "view_mode": "list",
            "views": [(tree_view.id, "list")],
            "search_view_id": (search_view.id, search_view.name),
            "target": "current",
            "domain": domain,
            "context": self._get_context_hide_fields(self.categ_id, self.invoiceset_id.state),
        }

    @api.model
    def _get_context_hide_fields(self, category, current_state="draft"):
        context = {}
        if not category.billable_item_quantity_field:
            context["hide_quantity"] = True
        else:
            context["billable_item_quantity_label"] = category.billable_item_quantity_label

        for idx in (1, 2, 3):
            for ttype in ("char", "int", "float", "bool"):
                field_name = getattr(category, f"aux_0{idx}_{ttype}_field", False)
                if not field_name:
                    context[f"hide_aux_0{idx}_{ttype}"] = True
                else:
                    context[f"aux_0{idx}_{ttype}_label"] = getattr(
                        category, f"aux_0{idx}_{ttype}_label", False
                    )

        if not category.aux_desc:
            context["hide_rendered_aux_desc"] = True
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
            self.env._("You are about to delete all lines associated with this product."),
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
        for record in self:
            record.env["account.selectable.item"].search(
                [("productlink_id", "=", record.id)]
            ).unlink()
            record.update_populated()

    def populate_selectable_items(self, productlink):
        """Populate account.selectable.item via SQL with sanitized identifiers.

        Note: billable_item_domain is kept for backward compatibility and is
        appended as raw SQL. Consider migrating it to a safe domain parser.
        """
        product = productlink.product_id
        category = product.product_tmpl_id.categ_id
        if not category or not category.billable_item_model_id:
            return

        model_name = category.billable_item_model_id.sudo().model
        table_name = model_name.replace(".", "_")

        quantity_field = category.billable_item_quantity_field

        billable_item_helper = self.env["account.billable.item"]
        partner_id_field = "partner_id"
        if billable_item_helper.inherits_from_account_billable_item(model_name):
            partner_id_field = getattr(self.env[model_name], "_billing_partner_id_name", "partner_id")

        aux_insert, aux_select = self._get_aux_fields(category)

        insert_cols = [
            sql.Identifier("id"),
            sql.Identifier("create_uid"),
            sql.Identifier("write_uid"),
            sql.Identifier("create_date"),
            sql.Identifier("write_date"),
            sql.Identifier("productlink_id"),
            sql.Identifier("billable_item_model"),
            sql.Identifier("billable_item_res_id"),
            sql.Identifier("partner_id"),
            sql.Identifier("quantity"),
            sql.Identifier("selected"),
        ]
        if aux_insert:
            for col in aux_insert.split(", "):
                insert_cols.append(sql.Identifier(col))

        select_cols = [
            sql.SQL("nextval('account_selectable_item_id_seq')"),
            sql.Placeholder(),
            sql.Placeholder(),
            sql.SQL("now()"),
            sql.SQL("now()"),
            sql.Placeholder(),
            sql.Placeholder(),
            sql.SQL("bt.id"),
            sql.SQL("bt.{}").format(sql.Identifier(partner_id_field)),
            sql.SQL("bt.{}").format(sql.Identifier(quantity_field)) if quantity_field else sql.SQL("1"),
            sql.SQL("TRUE"),
        ]
        if aux_select:
            for col in aux_select.split(", "):
                select_cols.append(sql.SQL("bt.{}").format(sql.Identifier(col)))

        query = sql.SQL("""
            INSERT INTO {dest} ({cols})
            SELECT {select_cols}
              FROM {src} bt
              JOIN res_partner rp ON bt.{partner_field} = rp.id
             WHERE rp.active
        """).format(
            dest=sql.Identifier("account_selectable_item"),
            cols=sql.SQL(", ").join(insert_cols),
            select_cols=sql.SQL(", ").join(select_cols),
            src=sql.Identifier(table_name),
            partner_field=sql.Identifier(partner_id_field),
        )

        params = [self.env.uid, self.env.uid, productlink.id, model_name]

        if billable_item_helper.exists_active_field(model_name):
            query += sql.SQL(" AND bt.active")

        if productlink.billable_item_domain:
            # Backward compat: appended raw SQL.
            query += sql.SQL(" AND ({})").format(sql.SQL(productlink.billable_item_domain))

        if productlink.product_id.product_tmpl_id.link_with_billable_items:
            query += sql.SQL(" AND bt.product_id = %s")
            params.append(productlink.product_id.id)

        try:
            self.env.cr.execute(query, tuple(params))
        except PsycopgError as err:
            raise UserError(self.env._("Error updating records: %s") % str(err)) from err

    @api.model
    def _get_aux_fields(self, category):
        aux_fields_insert = []
        aux_fields_select = []

        for idx in (1, 2, 3):
            for ttype in ("char", "int", "float", "bool"):
                src = getattr(category, f"aux_0{idx}_{ttype}_field", False)
                if not src:
                    continue
                aux_fields_insert.append(f"aux_0{idx}_{ttype}")
                aux_fields_select.append(src)

        return ", ".join(aux_fields_insert), ", ".join(aux_fields_select)

    def update_populated(self):
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT count(*) AS count
              FROM account_selectable_item
             WHERE productlink_id = %s
               AND selected
            """,
            (self.id,),
        )
        row = self.env.cr.dictfetchone() or {}
        self.write({"populated": bool(row.get("count"))})


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
        string="Invoice generation progress (%)",
        default=0.0,
        readonly=True,
    )
    stop_order = fields.Boolean(string="Active stop order", default=False)
