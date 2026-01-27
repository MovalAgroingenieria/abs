# 2026 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
# pylint: disable=protected-access
# pylint: disable=too-many-branches
# pylint: disable=duplicate-code


def _required_values_for(self, model, extra_vals=None):
    extra_vals = dict(extra_vals or {})
    vals = {}

    for name, field in model._fields.items():
        if not field.required:
            continue
        if field.compute or field.related:
            continue
        if name in extra_vals:
            continue
        if name in (
            "id",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "display_name",
        ):
            continue

        if field.type in ("char", "text", "html"):
            vals[name] = "x"
        elif field.type == "integer":
            vals[name] = 1
        elif field.type in ("float", "monetary"):
            vals[name] = 1.0
        elif field.type == "boolean":
            vals[name] = True
        elif field.type == "date":
            vals[name] = "2026-01-01"
        elif field.type == "datetime":
            vals[name] = "2026-01-01 00:00:00"
        elif field.type == "selection":
            selection = (
                field.selection(self.env)
                if callable(field.selection)
                else field.selection
            )
            vals[name] = selection[0][0] if selection else False
        elif field.type == "many2one":
            comodel = self.env[field.comodel_name]
            record = comodel.search([], limit=1)
            if not record:
                record = comodel.create(self._required_values_for(comodel))
            vals[name] = record.id

    vals.update(extra_vals)
    return vals
