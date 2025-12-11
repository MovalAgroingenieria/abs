# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

from typing import Any, Dict, List, Optional

from odoo import models


class CommonMetadata(models.AbstractModel):
    _name = "common.metadata"
    _description = "Metadata extraction utilities for Odoo models"

    # ------------------------------ Single field ------------------------------

    def get_field(
            self,
            model_name: str,
            field_name: str,
            exclude_nonpersistent: bool = True,
            exclude_related: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return metadata for a single field from ir.model.fields.

        Args:
            model_name: Technical model name (e.g., 'res.partner').
            field_name: Field technical name (e.g., 'name').
            exclude_nonpersistent: If True, only stored fields are considered.
            exclude_related: If True, exclude related fields.

        Returns:
            dict with field metadata or None if not found.
        """
        domain = [("model", "=", model_name), ("name", "=", field_name)]
        if exclude_nonpersistent:
            domain.append(("store", "=", True))
        if exclude_related:
            domain.append(("related", "=", False))

        field = self.env["ir.model.fields"].sudo().search(domain, limit=1)
        if not field:
            return None

        # Access attributes defensively: not all versions expose the same set
        def safe(attr: str, default=None):
            return getattr(field, attr, default)

        return {
            "model": model_name,
            "name": field_name,
            "field_description": safe("field_description"),
            "ttype": safe("ttype"),
            "relation": safe("relation"),
            "relation_field": safe("relation_field"),
            "on_delete": safe("on_delete"),
            "required": safe("required", False),
            "readonly": safe("readonly", False),
            "store": safe("store", False),
            "index": safe("index", False),
            # 'copy' is the canonical flag name on fields; older code used 'copied'
            "copy": safe("copy", True),
            "domain": safe("domain"),
            # Useful extras if available:
            "selection": safe("selection"),  # for selection fields
            "compute": safe("compute"),  # path to compute method
            "related": safe("related"),  # related path if any
            "help": safe("help"),
        }

    # ------------------------ Models referencing a model -----------------------

    def get_models_with_many2one(
            self,
            model_name: str,
            many2one_name: str = "",
            include_model: bool = True,
    ):
        """Return models having a Many2one referring to `model_name`.

        Args:
            model_name: Target model for Many2one relation.
            many2one_name: Optional field name filter (exact).
            include_model: If True, include the referenced model itself first.

        Returns:
            recordset of ir.model (unique, ordered).
        """
        ir_model = self.env["ir.model"].sudo()
        ir_model_fields = self.env["ir.model.fields"].sudo()

        # Start with the referenced model (optional)
        models_rs = ir_model.browse()
        ref_model = ir_model.search([("model", "=", model_name)], limit=1)
        if ref_model and include_model:
            models_rs |= ref_model

        # Find all Many2one fields that point to model_name
        domain = [("ttype", "=", "many2one"), ("relation", "=", model_name)]
        if many2one_name:
            domain.append(("name", "=", many2one_name))
        # Exclude transient models via the model relation
        m2o_fields = ir_model_fields.search(domain)
        if not m2o_fields:
            return models_rs

        # Collect unique model_ids, excluding the referenced model itself
        model_ids = {fld.model_id.id for fld in m2o_fields if fld.model != model_name}
        if model_ids:
            models_rs |= ir_model.browse(sorted(model_ids))
        return models_rs

    # ----------------------------- Multiple fields -----------------------------

    def get_fields(
            self,
            model_name: str,
            field_types: str,
            exclude_id: bool = True,
            exclude_nonpersistent: bool = True,
            exclude_related: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return (name, field_description) for fields of given types.

        Args:
            model_name: Technical model name.
            field_types: Comma-separated list (e.g., "integer,float").
            exclude_id: Exclude the 'id' pseudo-field.
            exclude_nonpersistent: If True, only stored fields.
            exclude_related: If True, exclude related fields.

        Returns:
            List of dicts with 'name' and 'field_description'.
        """
        types_list = [
            t.strip().lower() for t in (field_types or "").split(",") if t.strip()
        ]
        domain = [("model", "=", model_name)]
        if exclude_id:
            domain.append(("name", "!=", "id"))
        if exclude_nonpersistent:
            domain.append(("store", "=", True))
        if exclude_related:
            domain.append(("related", "=", False))
        if types_list:
            domain.append(("ttype", "in", types_list))

        fields_rs = self.env["ir.model.fields"].sudo().search(domain)
        return [
            {"name": f.name, "field_description": f.field_description}
            for f in fields_rs
        ]

    # --------------------------- Inheritance chain ----------------------------

    def get_inherited_models(self, model_name: str) -> List[str]:
        """Return inherited model names in the MRO (excluding the model itself).

        Notes:
            - Uses _name from classes in the MRO; safer than Python class names.
            - Order follows Python MRO from closest parent to base models.
        """
        result: List[str] = []
        if not model_name:
            return result

        try:
            model = self.env[model_name]

            # Get the class hierarchy (MRO) for this model
            # The first element is the model's own class, which we want to skip
            mro_classes = model.__class__.__mro__

            # Skip the first class (it's the model itself)
            # Start from index 1 to exclude 'self'
            for klass in mro_classes[1:]:
                parent_name = getattr(klass, "_name", None)
                if parent_name and parent_name not in result:
                    # Double-check we're not adding the model itself
                    if parent_name != model_name:
                        result.append(parent_name)
                    else:
                        # This shouldn't happen if we skip index 0, but just in case
                        continue

            # Additionally, check _inherit for v18 compatibility
            # This handles models that inherit using _inherit attribute
            if hasattr(model, '_inherit'):
                inherits = model._inherit
                if isinstance(inherits, str):
                    if inherits != model_name and inherits not in result:
                        result.append(inherits)
                elif isinstance(inherits, (list, tuple)):
                    for inh in inherits:
                        if inh != model_name and inh not in result:
                            result.append(inh)

            return result
        except KeyError:
            # Model doesn't exist in registry
            return result