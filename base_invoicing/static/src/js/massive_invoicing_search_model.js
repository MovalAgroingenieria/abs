/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {SearchModel} from "@web/search/search_model";

patch(SearchModel.prototype, "base_invoicing.massive_invoicing_search_model", {
    async load(config) {
        await this._super(...arguments);

        if (this.resModel !== "account.selectable.item") {
            return;
        }

        const context = config?.context || {};
        for (const item of Object.values(this.searchItems)) {
            if (!item?.fieldName) {
                continue;
            }
            const newLabel = context[`${item.fieldName}_label`];
            if (newLabel) {
                item.description = newLabel;
            }
        }

        document.body.setAttribute("data-res-model", "account.selectable.item");
        this.hideCustomGroupBy = true;

        if (context.hide_selectors) {
            document.body.setAttribute(
                "data-res-model-hide-selectors",
                "account.selectable.item"
            );
        } else {
            document.body.removeAttribute("data-res-model-hide-selectors");
        }
    },
});
