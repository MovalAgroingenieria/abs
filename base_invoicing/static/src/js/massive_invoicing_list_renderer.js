/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";

export class MassiveInvoicingListRenderer extends ListRenderer {
    getColumns() {
        const columns = super.getColumns();
        const context = this.props.list?.context || {};

        for (const col of columns) {
            if (!col?.name) {
                continue;
            }
            const labelKey =
                col.name === "quantity"
                    ? "billable_item_quantity_label"
                    : `${col.name}_label`;

            const newLabel = context[labelKey];
            if (newLabel) {
                col.label = newLabel;
            }
        }
        return columns;
    }

    get allowSelectors() {
        const context = this.props.list?.context || {};
        return context.hide_selectors ? false : super.allowSelectors;
    }
}

export class MassiveInvoicingListController extends ListController {
    onClickToReturn() {
        window.history.go(-1);
    }
}

registry.category("views").add("selectable_item_view_tree", {
    ...listView,
    Renderer: MassiveInvoicingListRenderer,
    Controller: MassiveInvoicingListController,
    buttonTemplate: "base_invoicing.ListView.Buttons",
});
