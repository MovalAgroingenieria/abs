# Propuesta: Vista híbrida para selección de items facturables

**Todo el código en base_invoicing, sin dependencias externas. Funciona para cualquier modelo billable.**

---

## 1. Objetivo

Al pulsar "Cargar y mostrar los registros" en un productlink, mostrar una lista que combine:
- Datos del **modelo origen** (ter.unit, res.fee, res.partner, etc.) con sus columnas reales
- Campos de control: `selected`, `productlink_id`, `quantity`, `partner_id`
- Checkbox para marcar qué items facturar

---

## 2. Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│  account.selectable.item (existente)                             │
│  + account_selectable_item VIEW (PostgreSQL, creada bajo demanda)│
│  JOIN tabla_billable (ter_unit, res_fee, res_partner, ...)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ir.model + ir.model.fields (dinámicos, modelo x_base_invoicing. │
│  selectable_<modelo_billable>)                                   │
│  Ej: x_base_invoicing.selectable_ter_unit                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ir.ui.view (list + search) + action                             │
│  Checkbox "selected" → RPC a account.selectable.item.write()     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Flujo

1. Usuario pulsa "Cargar y mostrar" en productlink
2. `populate_selectable_items(productlink)` crea los `account.selectable.item`
3. `_get_or_create_hybrid_view(category)`:
   - Si ya existe vista para el modelo billable → la reutiliza
   - Si no: crea vista SQL, ir.model, ir.model.fields, ir.ui.view, ir.model.access, acción
4. Abre acción con `res_model` = modelo híbrido, `domain` = `[('productlink_id','=',productlink.id)]`
5. Checkbox en la lista llama a RPC `account.selectable.item.toggle_selected(ids)` al cambiar

---

## 4. Query SQL auto-generada

```sql
SELECT
  CAST(row_number() OVER () AS integer) AS id,
  CAST(NULL AS integer) AS create_uid,
  CAST(NULL AS timestamp) AS create_date,
  CAST(NULL AS integer) AS write_uid,
  CAST(NULL AS timestamp) AS write_date,
  si.id AS selectable_item_id,
  si.productlink_id,
  si.selected,
  si.quantity,
  si.partner_id,
  bt.col1 AS x_col1,
  bt.col2 AS x_col2,
  ...
FROM account_selectable_item si
LEFT JOIN {billable_table} bt
  ON si.billable_item_model = '{model_name}'
  AND si.billable_item_res_id = bt.id
```

- `{billable_table}`: `Model._table` del modelo (ter_unit, res_fee, res_partner, …)
- `{model_name}`: nombre técnico (ter.unit, res.fee, res.partner, …)
- Columnas `x_*`: las de `aux_field_ids` o, si no hay, id + name del modelo billable

---

## 5. Modelo de configuración: `account.selectable.item.hybrid.view`

Modelo interno (sin UI de configuración). Almacena el estado por modelo billable:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| billable_model_id | Many2one → ir.model | Modelo billable (ter.unit, res.fee, …) |
| view_table | Char | Nombre de la vista SQL (x_base_invoicing_selectable_res_fee) |
| model_name | Char | Modelo Odoo (x_base_invoicing.selectable_res_fee) |
| model_id | Many2one → ir.model | ir.model creado |
| tree_view_id | Many2one → ir.ui.view | Vista list |
| search_view_id | Many2one → ir.ui.view | Vista search |
| action_id | Many2one → ir.actions.act_window | Acción para abrir |

Un registro por modelo billable. Se crea bajo demanda.

---

## 6. Mapeo SQL → Odoo field type

| SQL type (pg) | Odoo ttype |
|---------------|------------|
| boolean | boolean |
| bigint, integer | integer |
| double precision, numeric | float |
| text, character varying | char |
| date | date |
| timestamp without time zone | datetime |
| integer + sufijo _id | many2one (si hay relation) |

---

## 7. Estructura de archivos

```
base_invoicing/
├── models/
│   ├── __init__.py                    # + account_selectable_item_hybrid_view
│   └── account_selectable_item_hybrid_view.py   # NUEVO
├── static/src/js/
│   └── selectable_item_hybrid_list.esm.js       # NUEVO (checkbox RPC)
├── views/
│   └── account_selectable_item_hybrid_view_views.xml  # Opcional: form para debug
├── security/
│   └── ir.model.access.csv            # + acceso a account.selectable.item.hybrid.view
└── doc/
    └── PROPUESTA_VISTA_HIBRIDA_SELECTABLE_ITEMS.md
```

---

## 8. Detalle de implementación

### 8.1 `account_selectable_item_hybrid_view.py`

```python
# Funciones principales:

def _get_or_create_hybrid_view(self, category) -> "account.selectable.item.hybrid.view":
    """Obtiene o crea la vista híbrida para el modelo billable de la categoría."""
    # 1. Buscar existente por billable_model_id
    # 2. Si no existe: _create_hybrid_view(category)

def _create_hybrid_view(self, category) -> "account.selectable.item.hybrid.view":
    """Crea vista SQL + ir.model + ir.model.fields + vistas + action."""
    # 1. _build_sql_query(category) → query string
    # 2. CREATE OR REPLACE VIEW ...
    # 3. Inspeccionar columnas de la vista (pg_attribute) o generarlas desde aux_field_ids
    # 4. Crear ir.model (state='manual', model='x_base_invoicing.selectable_xxx')
    # 5. Crear ir.model.fields para cada columna
    # 6. ir.model.access (perm_read=1, resto=0)
    # 7. Crear ir.ui.view (list, search)
    # 8. Crear ir.actions.act_window
    # 9. init_models() para que el registry cargue el modelo

def _build_sql_query(self, category) -> str:
    """Genera la query SQL con las columnas de aux_field_ids o por defecto."""
    # Columnas: id (row_number), create_*, write_*, selectable_item_id,
    # productlink_id, selected, quantity, partner_id, x_col1, x_col2, ...

def _get_billable_columns(self, category) -> list[tuple[str, str]]:
    """[(nombre_sql, alias_x), ...] desde aux_field_ids o [('id','x_id'),('name','x_name')]."""
```

### 8.2 Nombre del modelo híbrido

Para evitar conflictos con puntos en nombres de modelo:
- `ter.unit` → `x_base_invoicing.selectable_ter_unit` (sustituir `.` por `_`)
- Tabla/vista: `x_base_invoicing_selectable_ter_unit`

### 8.3 Checkbox editable (JS)

El modelo híbrido es read-only. Widget o renderer que:
- En la columna `selected`, muestra checkbox
- Al cambiar: `await orm.write('account.selectable.item', [selectable_item_id], {selected: value})`
- Refresca la fila o el valor

Registro de vista custom con `js_class` en el list view del modelo híbrido.

### 8.4 `action_show_selectable_items` (productlink)

```python
def action_show_selectable_items(self):
    ...
    if self.invoiceset_id.state == "draft" and not self.number_of_selectable_items:
        self.populate_selectable_items(self)
    hybrid = self.env["account.selectable.item.hybrid.view"]._get_or_create_hybrid_view(
        self.categ_id
    )
    return {
        "type": "ir.actions.act_window",
        "res_model": hybrid.model_name,
        "domain": [("productlink_id", "=", self.id)],
        "context": {**ctx, "create": False},
        ...
    }
```

---

## 9. Permisos y seguridad

- `account.selectable.item.hybrid.view`: solo grupo de configuración (crear/editar)
- Modelo híbrido (`x_base_invoicing.selectable_*`): perm_read=1, perm_write/create/unlink=0
- El dominio `[('productlink_id','=',id)]` limita los registros visibles
- Toggle de `selected` vía RPC usa permisos de `account.selectable.item` (el usuario debe poder escribir)

---

## 10. Ciclo de vida

- **Creación**: bajo demanda al abrir "Cargar y mostrar"
- **Actualización**: si cambia `aux_field_ids`, borrar el registro híbrido existente y regenerar (DROP VIEW, unlink ir.model, etc.) o marcar como "stale" y regenerar en el próximo uso
- **Desinstalación**: hook que hace DROP VIEW de todas las vistas `x_base_invoicing_selectable_*` y unlink de ir.model/ir.model.fields asociados

---

## 11. Consideraciones

### 11.1 Modelos sin tabla física

Si el modelo billable es abstract o no tiene tabla, no se puede hacer JOIN. Comprobar `Model._table` antes de crear la vista.

### 11.2 res.partner

La tabla es `res_partner`. El modelo es `res.partner`. El JOIN funciona igual.

### 11.3 Registro del modelo en Odoo

Al crear `ir.model` con `state='manual'`, Odoo llama a `init_models`. El modelo se añade al registry. Para que el modelo use la vista (y no intente crear tabla), Odoo detecta que la "tabla" es una vista (`sql.table_kind` = view) y pone `Model._auto = False`. Eso está en `ir.model._add_manual_models`.

### 11.4 Reload del registry

Tras crear ir.model e ir.model.fields, hace falta que el registry se actualice. Odoo lo hace al crear ir.model (init_models). Para modelos manuales añadidos en runtime, puede hacer falta `env.registry.signal_changes()` o reiniciar el servidor. En la práctica, al crear ir.model desde el método de un action, el modelo puede no estar disponible hasta el próximo request. Solución: crear la vista en un paso previo (ej. al guardar la categoría) o usar `registry.setup_models` si estamos en el mismo proceso.

---

## 12. Alternativa sin vista SQL: componente OWL puro

Si la vista SQL dinámica resulta problemática (registry, multi-worker, etc.):

- **Enfoque**: componente OWL que carga registros del modelo billable con `orm.search_read`, domain calculado como en `populate_selectable_items`
- **Columnas**: de `aux_field_ids` o de la lista del modelo
- **Checkbox**: crea/elimina `account.selectable.item` vía RPC
- **Ventaja**: sin ir.model dinámico, sin vistas SQL
- **Inconveniente**: sin búsqueda/agrupación nativa de Odoo, más trabajo en JS

---

## 13. Resumen

| Componente | Descripción |
|------------|-------------|
| **account.selectable.item.hybrid.view** | Config por modelo billable, crea vista SQL + ir.model + vistas |
| **Query SQL** | JOIN account_selectable_item + tabla billable, columnas x_* desde aux_field_ids |
| **Modelo híbrido** | x_base_invoicing.selectable_<model>, read-only, una instancia por modelo billable |
| **Checkbox** | JS que llama a account.selectable.item.write() vía RPC |
| **Flujo** | "Cargar y mostrar" → populate → get_or_create_hybrid → abrir acción con domain |

Todo autocontenido en base_invoicing, sin dependencias externas, válido para cualquier modelo billable con tabla física.
