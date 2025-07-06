/** @odoo-module **/

import { registry } from '@web/core/registry';
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from '@web/views/list/list_view';

export class MassiveInvoicingListRenderer extends ListRenderer {
    setup() {
        super.setup();
        const columns = this.getColumns();
        const context = this.props.list.context;
        for (const column of columns) {
            if (column.name == 'quantity') {
                const newLabel = context['billable_item_quantity_label'];
                if (newLabel) {
                    column.label = newLabel;
                }
            } else {
                const newLabel = context[column.name + '_label'];
                if (newLabel) {
                    column.label = newLabel;
                }
            }
        }
        if (context['hide_selectors']) {
            this.props.allowSelectors = false;
        }
    }
};

registry.category('views').add('selectable_item_view_tree', {
    ...listView,
    Renderer: MassiveInvoicingListRenderer,
});
