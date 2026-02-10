# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

import html

from jinja2 import Template, TemplateError
from lxml import etree
from odoo import api, fields, models

from .product_category import get_jinja2_template_context


class AccountSelectableItem(models.Model):
    _name = "account.selectable.item"
    _description = "Selectable item for invoicing"

    productlink_id = fields.Many2one(
        comodel_name="account.invoiceset.productlink",
        ondelete="cascade",
        string="Product of invoice set",
        index=True,
        required=True,
    )
    billable_item_model = fields.Char(string="Billable item model: name", index=True)
    billable_item_res_id = fields.Many2oneReference(
        model_field="billable_item_model",
        string="Billable item model: reference",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        index=True,
    )
    quantity = fields.Float(digits=(32, 4))

    state = fields.Selection(
        related="productlink_id.invoiceset_id.state",
        string="State",
        readonly=True,
    )
    selected = fields.Boolean()
    selected_message = fields.Char(
        compute="_compute_selected_message",
        string="Selected (message)",
    )
    rendered_aux_desc = fields.Text(
        compute="_compute_rendered_aux_desc",
        string="Additional Information",
    )

    # Slots 1-20 for auxiliary fields (values stored as string for flexibility)
    aux_01 = fields.Char(string="Aux 1")
    aux_02 = fields.Char(string="Aux 2")
    aux_03 = fields.Char(string="Aux 3")
    aux_04 = fields.Char(string="Aux 4")
    aux_05 = fields.Char(string="Aux 5")
    aux_06 = fields.Char(string="Aux 6")
    aux_07 = fields.Char(string="Aux 7")
    aux_08 = fields.Char(string="Aux 8")
    aux_09 = fields.Char(string="Aux 9")
    aux_10 = fields.Char(string="Aux 10")
    aux_11 = fields.Char(string="Aux 11")
    aux_12 = fields.Char(string="Aux 12")
    aux_13 = fields.Char(string="Aux 13")
    aux_14 = fields.Char(string="Aux 14")
    aux_15 = fields.Char(string="Aux 15")
    aux_16 = fields.Char(string="Aux 16")
    aux_17 = fields.Char(string="Aux 17")
    aux_18 = fields.Char(string="Aux 18")
    aux_19 = fields.Char(string="Aux 19")
    aux_20 = fields.Char(string="Aux 20")

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends("selected")
    def _compute_selected_message(self):
        for record in self:
            record.selected_message = (
                record.env._("Selected")
                if record.selected
                else record.env._("Excluded")
            )

    @api.depends(
        "billable_item_model",
        "billable_item_res_id",
        "productlink_id.categ_id.aux_desc",
    )
    def _compute_rendered_aux_desc(self):
        for record in self:
            template_src = record.productlink_id.categ_id.aux_desc
            if (
                not template_src
                or not record.billable_item_model
                or not record.billable_item_res_id
            ):
                record.rendered_aux_desc = ""
                continue

            billable_item = record.env[record.billable_item_model].browse(
                record.billable_item_res_id
            )
            if not billable_item.exists():
                record.rendered_aux_desc = ""
                continue

            productlink = record.productlink_id
            invoiceset = productlink.invoiceset_id if productlink else None
            ctx = get_jinja2_template_context(
                record.env,
                billable_item,
                invoiceset=invoiceset,
                productlink=productlink,
                product=productlink.product_id if productlink else None,
                partner=record.partner_id if record.partner_id else None,
                quantity=record.quantity,
            )
            try:
                rendered = Template(template_src).render(**ctx)
            except TemplateError as err:
                rendered = record.env._("Error in template: %(error)s", error=str(err))

            if "|" in template_src:
                rendered = rendered.replace("|", "\n")

            record.rendered_aux_desc = rendered

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_select_items(self):
        self.write({"selected": True})
        self._update_productlink_populated()

    def action_deselect_items(self):
        self.write({"selected": False})
        self._update_productlink_populated()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._update_productlink_populated()
        return records

    def write(self, vals):
        if not {"selected", "productlink_id"} & set(vals):
            return super().write(vals)
        productlinks_before = self.mapped("productlink_id").exists()
        res = super().write(vals)
        productlinks_after = self.mapped("productlink_id").exists()
        self._update_productlink_populated_for_links(
            productlinks_before | productlinks_after
        )
        return res

    def unlink(self):
        productlinks = self.mapped("productlink_id").exists()
        res = super().unlink()
        self._update_productlink_populated_for_links(productlinks)
        return res

    def _update_productlink_populated(self):
        self._update_productlink_populated_for_links(
            self.mapped("productlink_id").exists()
        )

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self.env.context.get("selectable_items_categ_id"),)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type not in ("list", "search"):
            return arch, view

        categ_id = self.env.context.get("selectable_items_categ_id")
        category = self.env["product.category"].browse(categ_id) if categ_id else None
        if not category or not category.exists():
            # No category: hide rendered_aux_desc, no aux columns
            self._inject_selectable_item_view_arch(arch, view_type, None)
            return arch, view

        self._inject_selectable_item_view_arch(arch, view_type, category)
        return arch, view

    def _inject_selectable_item_view_arch(self, arch, view_type, category):
        """Inject aux columns and adjust visibility from category.aux_field_ids."""
        if view_type == "list":
            self._inject_list_aux_columns(arch, category)
        else:
            self._inject_search_aux_fields(arch, category)

    def _inject_list_aux_columns(self, arch, category):
        quantity_node = arch.find(".//field[@name='quantity']")
        rendered_node = arch.find(".//field[@name='rendered_aux_desc']")
        insert_after = quantity_node if quantity_node is not None else None
        if rendered_node is not None:
            if category and category.aux_desc:
                rendered_node.set("string", self.env._("Additional Information"))
            else:
                rendered_node.set("column_invisible", "True")

        if not category or not category.aux_field_ids:
            return

        # Inject aux field columns after quantity
        for idx, line in enumerate(category.aux_field_ids.sorted("sequence")[:20], 1):
            slot = f"aux_{idx:02d}"
            label = (
                line.custom_label
                or (line.field_id.field_description if line.field_id else "")
                or line.field_id.name
                or slot
            )
            label_safe = html.escape(str(label), quote=True)
            field_el = etree.Element("field", name=slot, string=label_safe)
            if insert_after is not None:
                insert_after.addnext(field_el)
                insert_after = field_el
            else:
                # Prepend to first field
                first = arch.find(".//field")
                if first is not None:
                    first.addprevious(field_el)

    def _inject_search_aux_fields(self, arch, category):
        if not category or not category.aux_field_ids:
            return
        search_node = arch.find(".")
        if search_node is None:
            return
        field_group = arch.find(".//field[@name='partner_id']")
        insert_after = field_group
        for idx, line in enumerate(category.aux_field_ids.sorted("sequence")[:20], 1):
            slot = f"aux_{idx:02d}"
            label = (
                line.custom_label
                or (line.field_id.field_description if line.field_id else "")
                or line.field_id.name
                or slot
            )
            label_safe = html.escape(str(label), quote=True)
            field_el = etree.Element("field", name=slot, string=label_safe)
            if insert_after is not None:
                insert_after.addnext(field_el)
                insert_after = field_el

        group_node = arch.find(".//group[@expand='0']")
        if group_node is not None:
            for idx, line in enumerate(
                category.aux_field_ids.sorted("sequence")[:20], 1
            ):
                slot = f"aux_{idx:02d}"
                label = (
                    line.custom_label
                    or (line.field_id.field_description if line.field_id else "")
                    or line.field_id.name
                    or slot
                )
                label_safe = html.escape(str(label), quote=True)
                filter_el = etree.Element(
                    "filter",
                    name=f"grouped_by_{slot}",
                    string=label_safe,
                    context=f"{{'group_by': '{slot}'}}",
                )
                group_node.append(filter_el)

    def _update_productlink_populated_for_links(self, productlinks):
        productlinks = productlinks.exists()
        if not productlinks:
            return

        data = self.env["account.selectable.item"].read_group(
            [("productlink_id", "in", productlinks.ids), ("selected", "=", True)],
            ["productlink_id"],
            ["productlink_id"],
        )
        counts = {d["productlink_id"][0]: d["productlink_id_count"] for d in data}

        for productlink in productlinks:
            if productlink.display_type in ("line_section", "line_note"):
                productlink.write({"populated": True})
            else:
                productlink.write({"populated": bool(counts.get(productlink.id, 0))})
