# 2025-2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access

import logging
import re

from psycopg2 import ProgrammingError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql as odoo_sql

_logger = logging.getLogger(__name__)

_PREFIX = "x_base_invoicing_selectable_"


def _model_to_suffix(model_name):
    """Convert model name to safe suffix: ter.unit -> ter_unit."""
    return (model_name or "").replace(".", "_").replace("-", "_").lower()


def _build_suffix(model_name, category_id):
    """Build suffix: model + category id for uniqueness. E.g. ter_parcel_42."""
    base = _model_to_suffix(model_name)
    if not base:
        return ""
    if category_id is not None:
        return f"{base}_{category_id}"
    return base


class AccountSelectableItemHybridView(models.Model):
    _name = "account.selectable.item.hybrid.view"
    _description = "Hybrid SQL view for selectable items (config per billable model + category)"

    billable_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Billable model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product category",
        ondelete="cascade",
        index=True,
    )
    view_table = fields.Char(
        string="View table name",
        compute="_compute_view_table",
        store=True,
    )
    model_name = fields.Char(
        string="Hybrid model name",
        compute="_compute_model_name",
        store=True,
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Hybrid model",
        readonly=True,
        ondelete="set null",
    )
    tree_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="List view",
        readonly=True,
        ondelete="set null",
    )
    search_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Search view",
        readonly=True,
        ondelete="set null",
    )
    pivot_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Pivot view",
        readonly=True,
        ondelete="set null",
    )

    _sql_constraints = [
        (
            "billable_model_category_uniq",
            "UNIQUE(billable_model_id, category_id)",
            "A hybrid view already exists for this billable model and category.",
        ),
    ]

    @api.depends("billable_model_id.model", "category_id")
    def _compute_view_table(self):
        for rec in self:
            suffix = _build_suffix(
                rec.billable_model_id.model if rec.billable_model_id else "",
                rec.category_id.id if rec.category_id else None,
            )
            rec.view_table = f"{_PREFIX}{suffix}" if suffix else ""

    @api.depends("billable_model_id.model", "category_id")
    def _compute_model_name(self):
        for rec in self:
            suffix = _build_suffix(
                rec.billable_model_id.model if rec.billable_model_id else "",
                rec.category_id.id if rec.category_id else None,
            )
            rec.model_name = f"x_base_invoicing.selectable_{suffix}" if suffix else ""

    @api.model
    def _get_or_create_for_category(self, category):
        """Get or create hybrid view for the category's billable model + category."""
        if not category or not category.billable_item_model_id:
            return self.env["account.selectable.item.hybrid.view"]
        model_id = category.billable_item_model_id.id
        domain = [
            ("billable_model_id", "=", model_id),
            ("category_id", "=", category.id),
        ]
        hybrid = self.search(domain, limit=1)
        if not hybrid:
            hybrid = self.create({
                "billable_model_id": model_id,
                "category_id": category.id,
            })
            hybrid._build_hybrid_view(category)
        elif not hybrid.model_id:
            hybrid._build_hybrid_view(category)
        return hybrid

    def _build_hybrid_view(self, category):
        """Create PostgreSQL view + ir.model + ir.model.fields + ir.ui.view + access."""
        self.ensure_one()
        if self.model_id:
            return
        billable_model = self.billable_model_id
        model_name = billable_model.model
        billable_table = self.env[model_name]._table

        # 1. Build SQL query (uses filtered columns that exist in DB)
        query, bt_cols_raw = self._build_sql_query(
            category, model_name, billable_table
        )
        view_table = self.view_table

        # 2. Create PostgreSQL view
        self._create_view(view_table, query)

        # 3. Define columns for ir.model.fields (must match SQL columns)
        field_specs = self._get_field_specs(category, model_name, bt_cols_raw)

        # 4. Create ir.model with fields
        IrModel = self.env["ir.model"].sudo()
        IrModelFields = self.env["ir.model.fields"].sudo()
        IrModelAccess = self.env["ir.model.access"].sudo()
        View = self.env["ir.ui.view"].sudo()

        # Prepare field vals for ir.model.fields (model_id set by inverse)
        # Note: ir.model.fields has no 'sequence' field, do not pass it
        field_vals_list = []
        for fname, desc, ttype, relation in field_specs:
            field_vals_list.append({
                "name": fname,
                "field_description": desc,
                "ttype": ttype,
                "state": "manual",
                "relation": relation or False,
                "store": True,
            })

        # Create ir.model with field_id
        model_vals = {
            "name": f"Selectable items ({billable_model.name})",
            "model": self.model_name,
            "state": "manual",
            "field_id": [(0, 0, fv) for fv in field_vals_list],
        }
        model_rec = IrModel.create(model_vals)
        self.model_id = model_rec.id

        # 5. Create ir.model.access (read only)
        group_invoice = self.env.ref("account.group_account_invoice", raise_if_not_found=False)
        if group_invoice:
            IrModelAccess.create({
                "name": f"Read {self.model_name}",
                "model_id": model_rec.id,
                "group_id": group_invoice.id,
                "perm_read": True,
                "perm_write": False,
                "perm_create": False,
                "perm_unlink": False,
            })

        # 6. Create mass Activate/Deactivate server actions (for dropdown + header)
        # Set groups_id to bypass write check (hybrid model is read-only; we write to account.selectable.item)
        group_invoice = self.env.ref("account.group_account_invoice", raise_if_not_found=False)
        action_vals = {"groups_id": [(6, 0, group_invoice.ids)]} if group_invoice else {}
        IrActServer = self.env["ir.actions.server"].sudo()
        action_select = IrActServer.create({
            "name": _("Activate"),
            "model_id": model_rec.id,
            "binding_model_id": model_rec.id,
            "binding_type": "action",
            "binding_view_types": "list,form",
            "state": "code",
            "code": """selectable_ids = records.mapped('x_selectable_item_id')
if selectable_ids:
    env['account.selectable.item'].browse(selectable_ids).write({'selected': True})
""",
            **action_vals,
        })
        action_deselect = IrActServer.create({
            "name": _("Deactivate"),
            "model_id": model_rec.id,
            "binding_model_id": model_rec.id,
            "binding_type": "action",
            "binding_view_types": "list,form",
            "state": "code",
            "code": """selectable_ids = records.mapped('x_selectable_item_id')
if selectable_ids:
    env['account.selectable.item'].browse(selectable_ids).write({'selected': False})
""",
            **action_vals,
        })
        self.env.registry.clear_cache()

        # 7. Create tree view with header buttons (editable="bottom" so toggle works)
        tree_fields = self._build_tree_view_fields(field_specs)
        header = (
            f'<header>'
            f'<button name="{action_select.id}" type="action" string="{_("Activate")}" class="btn-primary" icon="fa-check-square-o"/>'
            f'<button name="{action_deselect.id}" type="action" string="{_("Deactivate")}" class="btn-secondary" icon="fa-square-o"/>'
            f"</header>"
        )
        tree_arch = (
            f'<?xml version="1.0"?><list create="false" delete="false" editable="bottom">'
            f"{header}{tree_fields}</list>"
        )
        tree_view = View.create({
            "name": f"Selectable items hybrid ({model_name})",
            "type": "list",
            "model": self.model_name,
            "arch": tree_arch,
        })
        self.tree_view_id = tree_view.id

        # 8. Create search view with group by for all fields
        search_fields = "".join(
            f'<field name="{fname}"/>' for fname, _desc, _t, _r in field_specs
        )
        group_by_fields = self._build_search_groupby(field_specs)
        search_arch = (
            f'<?xml version="1.0"?><search string="Search">'
            f'{search_fields}'
            f'<filter name="selected_yes" string="Selected" domain="[(\'x_selected\', \'=\', True)]"/>'
            f'<filter name="selected_no" string="Not selected" domain="[(\'x_selected\', \'=\', False)]"/>'
            f'<group expand="0" string="Group By">{group_by_fields}</group>'
            f"</search>"
        )
        search_view = View.create({
            "name": f"Search selectable hybrid ({model_name})",
            "type": "search",
            "model": self.model_name,
            "arch": search_arch,
        })
        self.search_view_id = search_view.id

        # 9. Create pivot view (groupable aux columns + x_quantity as measure)
        pivot_fields = self._build_pivot_view_fields(field_specs)
        pivot_arch = (
            f'<?xml version="1.0"?><pivot string="Selectable Items">'
            f"{pivot_fields}</pivot>"
        )
        pivot_view = View.create({
            "name": f"Pivot selectable hybrid ({model_name})",
            "type": "pivot",
            "model": self.model_name,
            "arch": pivot_arch,
        })
        self.pivot_view_id = pivot_view.id

        return self

    def _build_pivot_view_fields(self, field_specs):
        """Build pivot: row=groupable fields, measure=x_quantity."""
        groupable_types = {"many2one", "char", "selection", "boolean"}
        row_parts = []
        for fname, _desc, ttype, _relation in field_specs:
            if fname in ("x_selectable_item_id", "x_productlink_id"):
                continue
            if ttype in groupable_types:
                row_parts.append(f'<field name="{fname}" type="row"/>')
        # Measure: quantity
        measure = '<field name="x_quantity" type="measure"/>'
        return "".join(row_parts) + measure

    def _build_search_groupby(self, field_specs):
        """Build group by filters for many2one and char fields."""
        groupable_types = {"many2one", "char", "selection", "boolean"}
        parts = []
        for fname, desc, ttype, _relation in field_specs:
            if fname == "x_selectable_item_id":
                continue  # Skip internal id
            if ttype in groupable_types:
                safe_name = fname.replace(".", "_")
                esc_desc = desc.replace('"', "&quot;")
                parts.append(
                    f'<filter name="group_{safe_name}" string="{esc_desc}" '
                    f"context=\"{{'group_by': '{fname}'}}\"/>"
                )
        return "".join(parts)

    def _build_sql_query(self, category, model_name, billable_table):
        """Build the SQL for the hybrid view. Returns (query, bt_cols_raw)."""
        si_table = "account_selectable_item"
        bt_alias = "bt"

        # Columns from account_selectable_item (x_ prefix required for manual fields)
        si_cols = [
            "si.id AS x_selectable_item_id",
            "si.productlink_id AS x_productlink_id",
            "si.selected AS x_selected",
            "si.quantity AS x_quantity",
            "si.partner_id AS x_partner_id",
        ]

        # Columns from billable table (only those that exist in DB)
        bt_cols_raw = self._get_billable_columns(
            category, model_name, billable_table, bt_alias
        )
        bt_cols = [c[0] for c in bt_cols_raw]

        # Build SELECT with row_number for id
        select_parts = [
            "CAST(row_number() OVER () AS integer) AS id",
            "CAST(NULL AS integer) AS create_uid",
            "CAST(NULL AS timestamp without time zone) AS create_date",
            "CAST(NULL AS integer) AS write_uid",
            "CAST(NULL AS timestamp without time zone) AS write_date",
        ] + si_cols + bt_cols

        query = f"""
        SELECT {", ".join(select_parts)}
        FROM {si_table} si
        LEFT JOIN {billable_table} {bt_alias}
          ON si.billable_item_model = %s
          AND si.billable_item_res_id = {bt_alias}.id
        """
        return query, bt_cols_raw

    def _get_model_field_column(self, model, field_name):
        """
        Get the database column name from the actual model field object.
        Respects inheritance: uses model._fields[field_name].column.
        Returns None if field does not exist or is not stored.
        """
        odoo_field = model._fields.get(field_name)
        if not odoo_field:
            return None
        if not getattr(odoo_field, "store", True):
            return None
        col = getattr(odoo_field, "column", None)
        if col is None:
            return field_name
        if isinstance(col, (list, tuple)):
            return col[0] if col else field_name
        return col or field_name

    def _get_billable_columns(self, category, model_name, billable_table, bt_alias):
        """Return [(sql_expr, alias, field_info), ...] for billable table columns.
        Uses the actual model field object (model._fields) for the column name,
        so inheritance is respected.
        """
        try:
            model = self.env[model_name]
        except KeyError:
            return []
        cols = []
        if category.aux_field_ids:
            for idx, line in enumerate(
                category.aux_field_ids.sorted("sequence")[:20], start=1
            ):
                if not line.field_id:
                    continue
                ir_field = line.field_id
                col_name = self._get_model_field_column(model, ir_field.name)
                if col_name is None:
                    _logger.debug(
                        "[base_invoicing] Skipping field %s: not found or not stored on %s",
                        ir_field.name,
                        model_name,
                    )
                    continue
                alias = f"x_aux_{idx:02d}"
                cols.append((f"{bt_alias}.{col_name} AS {alias}", alias, ir_field))
        else:
            # Default: id and name from model fields (use actual column)
            id_col = self._get_model_field_column(model, "id")
            if id_col:
                cols.append((f"{bt_alias}.{id_col} AS x_id", "x_id", None))
            name_col = self._get_model_field_column(model, "name")
            if name_col:
                cols.append((f"{bt_alias}.{name_col} AS x_name", "x_name", None))
        return cols

    def _get_field_specs(self, category, model_name, bt_cols_raw):
        """Return [(field_name, description, ttype, relation), ...] for ir.model.fields.
        Must match the columns in bt_cols_raw (only those that exist in DB).
        """
        specs = [
            ("x_selectable_item_id", "Selectable Item ID", "integer", ""),
            ("x_productlink_id", "Product link", "many2one", "account.invoiceset.productlink"),
            ("x_selected", "Selected", "boolean", ""),
            ("x_quantity", "Quantity", "float", ""),
            ("x_partner_id", "Customer", "many2one", "res.partner"),
        ]
        custom_labels = {
            line.field_id.id: line.custom_label
            for line in (category.aux_field_ids or [])
            if line.field_id
        }
        for _sql_expr, alias, field_info in bt_cols_raw:
            if field_info:
                f = field_info
                ttype = f.ttype
                if ttype in ("one2many", "many2many", "binary", "html"):
                    ttype = "char"
                desc = custom_labels.get(f.id) or f.field_description or alias
                specs.append((alias, desc, ttype, f.relation or ""))
            else:
                if alias == "x_id":
                    specs.append(("x_id", "ID", "integer", ""))
                elif alias == "x_name":
                    specs.append(("x_name", "Name", "char", ""))
        return specs

    def _build_tree_view_fields(self, field_specs):
        """Build XML field elements for list view."""
        parts = []
        for fname, desc, ttype, _relation in field_specs:
            extra = ""
            if fname == "x_selected":
                extra = ' widget="selectable_hybrid_toggle"'
            elif fname == "x_selectable_item_id":
                extra = ' column_invisible="1"'
            escaped_desc = desc.replace('"', "&quot;")
            parts.append(f'<field name="{fname}" string="{escaped_desc}"{extra}/>')
        return "".join(parts)

    def unlink(self):
        """Drop PostgreSQL view before unlinking."""
        for rec in self:
            if rec.view_table:
                try:
                    drop_sql = odoo_sql.SQL(
                        "DROP VIEW IF EXISTS %s CASCADE",
                        odoo_sql.SQL.identifier(rec.view_table),
                    )
                    self.env.cr.execute(drop_sql)
                except ProgrammingError:
                    pass
        return super().unlink()

    def _create_view(self, view_table, query):
        """Create or replace PostgreSQL view."""
        if not re.match(r"^[a-z0-9_]+$", view_table):
            raise ValidationError(_("Invalid view table name: %s") % view_table)
        drop_sql = odoo_sql.SQL("DROP VIEW IF EXISTS %s CASCADE", odoo_sql.SQL.identifier(view_table))
        self.env.cr.execute(drop_sql)
        try:
            model_name = self.billable_model_id.model
            # Query contains %s for model_name; view_table is safe (regex-validated)
            view_quoted = odoo_sql.SQL.identifier(view_table).code
            create_stmt = f"CREATE VIEW {view_quoted} AS ({query})"
            self.env.cr.execute(create_stmt, (model_name,))
        except ProgrammingError as e:
            raise UserError(
                _("Error creating hybrid view %(view)s: %(error)s")
                % {"view": view_table, "error": str(e)}
            ) from e
