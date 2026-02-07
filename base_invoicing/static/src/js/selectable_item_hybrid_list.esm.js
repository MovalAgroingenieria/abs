/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    BooleanToggleField,
    booleanToggleField,
} from "@web/views/fields/boolean_toggle/boolean_toggle_field";
import { ListBooleanToggleField } from "@web/views/fields/boolean_toggle/list_boolean_toggle_field";
import { useService } from "@web/core/utils/hooks";

async function writeSelectableItem(orm, record, newValue) {
    const selectableItemId = record.data.x_selectable_item_id;
    if (selectableItemId === undefined || selectableItemId === false) {
        return false;
    }
    await orm.write("account.selectable.item", [selectableItemId], {
        selected: newValue,
    });
    await record.update({ x_selected: newValue }, { save: false });
    return true;
}

/**
 * Field widget for the "selected" column in the hybrid selectable items list.
 * Writes to account.selectable.item via RPC instead of the (read-only) hybrid model.
 * Forces readonly=false so the toggle is clickable even when the hybrid model has no write access.
 */
class SelectableHybridBooleanToggleField extends BooleanToggleField {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onChange(newValue) {
        this.state.value = newValue;
        try {
            await writeSelectableItem(
                this.orm,
                this.props.record,
                newValue
            );
        } catch (e) {
            this.state.value = !newValue;
            throw e;
        }
    }
}

/**
 * List-specific version: click works without requiring record.isInEdition,
 * because the hybrid model is read-only and rows never enter edit mode.
 */
class ListSelectableHybridBooleanToggleField extends ListBooleanToggleField {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onClick() {
        if (this.props.readonly) return;
        const current = this.props.record.data.x_selected;
        const newValue = !current;
        this.state.value = newValue;
        try {
            const ok = await writeSelectableItem(
                this.orm,
                this.props.record,
                newValue
            );
            if (!ok) this.state.value = current;
        } catch (e) {
            this.state.value = current;
            throw e;
        }
    }
}

export const selectableHybridBooleanToggleField = {
    ...booleanToggleField,
    component: SelectableHybridBooleanToggleField,
    displayName: _t("Toggle"),
    extractProps({ options }, dynamicInfo) {
        return {
            autosave: "autosave" in options ? Boolean(options.autosave) : true,
            readonly: false, // Always allow toggle; we write to account.selectable.item
        };
    },
};

export const listSelectableHybridBooleanToggleField = {
    ...selectableHybridBooleanToggleField,
    component: ListSelectableHybridBooleanToggleField,
};

registry.category("fields").add("selectable_hybrid_toggle", selectableHybridBooleanToggleField);
registry.category("fields").add("list.selectable_hybrid_toggle", listSelectableHybridBooleanToggleField);
