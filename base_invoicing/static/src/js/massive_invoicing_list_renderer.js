/** @odoo-module **/

import {registry} from "@web/core/registry";
import {ListController} from "@web/views/list/list_controller";
import {ListRenderer} from "@web/views/list/list_renderer";
import {listView} from "@web/views/list/list_view";

export class MassiveInvoicingListRenderer extends ListRenderer {
    setup() {
        super.setup();

        const context = this.props.list?.context || {};
        const columns = this.getColumns();

        for (const column of columns) {
            if (!column?.name) {
                continue;
            }

            const labelKey =
                column.name === "quantity"
                    ? "billable_item_quantity_label"
                    : `${column.name}_label`;

            const newLabel = context[labelKey];
            if (newLabel) {
                column.label = newLabel;
            }
        }

        if (context.hide_selectors) {
            this.props.allowSelectors = false;
        }
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
