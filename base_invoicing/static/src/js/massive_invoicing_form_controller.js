/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from '@web/views/form/form_controller';
import { formView } from '@web/views/form/form_view';
import { useService } from "@web/core/utils/hooks";

const INTERVAL = 2000;
let previous_background = false;
let current_background = false;

export class MassiveInvoicingFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService('orm');
        if (!this._intervalId) {
            this._intervalId = setInterval(() => {
                previous_background = current_background;
                this.orm.call('account.invoiceset',
                              'background_calculation_active',
                              [[this.props.resId]]
                    ).then((result) => {
                        current_background = result;
                        if (current_background ||
                            (!current_background && previous_background)) {
                            // Provisional
                            // console.log('Refresh...');
                            this.model.load();
                        }
                    });
            }, INTERVAL);
        }
    }

    async beforeLeave() {
        await super.beforeLeave();
        if (this._intervalId) {
            clearInterval(this._intervalId);
        }
    }
};

registry.category('views').add('invoiceset_view_form', {
    ...formView,
    Controller: MassiveInvoicingFormController,
});
