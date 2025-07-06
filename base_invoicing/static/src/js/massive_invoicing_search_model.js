/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { SearchModel } from '@web/search/search_model';

// NOTE: It is not possible to use "registry.category('views').add" here
// (different from the "ListRenderer" class
// -see "massive_invoicing_list_renderer.js"); therefore, a patch is required.

patch(SearchModel.prototype, 'massive_invoicing_search_model', {
    async load(config) {
        // This method is asynchronous, so await is required
        // (before calling "_super").
        await this._super(...arguments);
        if (this.resModel == 'account.selectable.item') {
            const context = config.context || {};
            for (const [key, item] of Object.entries(this.searchItems)) {
                const newLabel = context[`${item.fieldName}_label`];
                if (newLabel) {
                      item.description = newLabel;
                }
            }
            // Hide the "Add Custom Filter" button (see the
            // "o_add_custom_filter_menu" CSS class in "base_invoicing.scss").
            document.body.setAttribute("data-res-model", "account.selectable.item");
            // Hide the "Add Custom Group" button (see the "load" method of the
            // "SearchModel" class in the "web" module).
            this.hideCustomGroupBy = true;
            // if "hide_selectors" then remove the "Filter" button (all).
            // Important: this runs every time we render the search view, but the
            // "data-res-model-hide-selectors" attribute remains from the last
            // render, so it needs to be deleted.
            if (context['hide_selectors']) {
                document.body.setAttribute("data-res-model-hide-selectors", "account.selectable.item");
            } else {
                document.body.removeAttribute("data-res-model-hide-selectors");
            }
        }
    },
});