# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from typing import Any, Dict, List, Optional

from odoo import models


class CommonMetadata(models.AbstractModel):
    _name = "common.metadata"
    _description = "Metadata extraction utilities for Odoo models"

    # ------------------------------ Model description --------------------------

    def get_description(self, model_name: str) -> Optional[str]:
        """Return the description (name) of the model from ir.model.

        Used e.g. when configuring a category to show the billable item model
        description (e.g. \"Partner of parcel\" for ter.parcel.partnerlink).
        """
        if not model_name:
            return None
        model = (
            self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        )
        return model.name if model else None

    # ------------------------------ Single field ------------------------------

    def get_field(
        self,
        model_name: str,
        field_name: str,
        exclude_nonpersistent: bool = True,
        exclude_related: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return metadata for a single field from ir.model.fields."""
        if not model_name or not field_name:
            return None

        domain = [("model", "=", model_name), ("name", "=", field_name)]
        if exclude_nonpersistent:
            domain.append(("store", "=", True))
        if exclude_related:
            domain.append(("related", "=", False))

        field = self.env["ir.model.fields"].sudo().search(domain, limit=1)
        if not field:
            return None

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
            "copy": safe("copy", True),
            "domain": safe("domain"),
            "selection": safe("selection"),
            "compute": safe("compute"),
            "related": safe("related"),
            "help": safe("help"),
        }

    # ------------------------ Models referencing a model -----------------------

    def get_models_with_many2one(
        self,
        model_name: str,
        many2one_name: str = "",
        include_model: bool = True,
        exclude_transient: bool = True,
    ):
        """Return ir.model records having a Many2one referring to `model_name`."""
        ir_model = self.env["ir.model"].sudo()
        ir_model_fields = self.env["ir.model.fields"].sudo()

        models_rs = ir_model.browse()
        if not model_name:
            return models_rs

        ref_model = ir_model.search([("model", "=", model_name)], limit=1)
        if ref_model and include_model:
            models_rs |= ref_model

        domain = [("ttype", "=", "many2one"), ("relation", "=", model_name)]
        if many2one_name:
            domain.append(("name", "=", many2one_name))

        m2o_fields = ir_model_fields.search(domain)
        if not m2o_fields:
            return models_rs

        model_ids = {fld.model_id.id for fld in m2o_fields if fld.model != model_name}
        if not model_ids:
            return models_rs

        extra_domain = [("id", "in", sorted(model_ids))]
        if exclude_transient:
            extra_domain.append(("transient", "=", False))

        models_rs |= ir_model.search(extra_domain, order="model")
        return models_rs

    # ----------------------------- Multiple fields -----------------------------

    def get_fields(
        self, model_name: str, field_types: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """Return (name, field_description) for fields of given types.

        Kwargs: exclude_id (default True), exclude_nonpersistent (default True),
        exclude_related (default False).
        """
        if not model_name:
            return []
        exclude_id = kwargs.get("exclude_id", True)
        exclude_nonpersistent = kwargs.get("exclude_nonpersistent", True)
        exclude_related = kwargs.get("exclude_related", False)
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

        fields_rs = self.env["ir.model.fields"].sudo().search(domain, order="name")
        result = []
        for fld in fields_rs:
            result.append(
                {
                    "name": fld.name,
                    "field_description": fld.field_description or fld.name,
                }
            )
        return result

    # --------------------------- Inheritance chain ----------------------------

    def get_inherited_models(self, model_name: str) -> List[str]:
        """Return inherited model names (excluding the model itself)."""
        if not model_name:
            return []

        try:
            model = self.env[model_name]
        except KeyError:
            return []

        result: List[str] = []

        inherits = getattr(model, "_inherit", None)
        if isinstance(inherits, str):
            if inherits and inherits != model_name:
                result.append(inherits)
        elif isinstance(inherits, (list, tuple)):
            for inh in inherits:
                if inh and inh != model_name and inh not in result:
                    result.append(inh)

        # Add MRO names that map to real registered models only
        for klass in model.__class__.__mro__[1:]:
            parent_name = getattr(klass, "_name", None)
            if not parent_name or parent_name == model_name or parent_name in result:
                continue
            if parent_name in self.env:
                result.append(parent_name)

        return result
