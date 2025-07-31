/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from '@web/views/form/form_controller';
import { formView } from '@web/views/form/form_view';
import { useService } from "@web/core/utils/hooks";

const INTERVAL = 2000;
let previous_background = false;
let current_background = false;
let refresh_interval = false;

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

    async onPagerUpdate({ offset, resIds }) {
        await super.onPagerUpdate({ offset, resIds });
        if (this._intervalId) {
            clearInterval(this._intervalId);
        }
        previous_background = false;
        current_background = false;
        this._intervalId = setInterval(() => {
            previous_background = current_background;
            this.orm.call('account.invoiceset',
                          'background_calculation_active',
                          [[resIds[offset]]]
                ).then((result) => {
                    current_background = result;
                    if (current_background ||
                        (!current_background && previous_background)) {
                        this.model.load();
                    }
                });
        }, INTERVAL);
    }

    async deleteRecord() {
        await super.deleteRecord();
        refresh_interval = true;
    }

    updateURL() {
        super.updateURL();
        if (refresh_interval) {
            refresh_interval = false;
            if (this._intervalId) {
                clearInterval(this._intervalId);
            }
            previous_background = false;
            current_background = false;
            this._intervalId = setInterval(() => {
                previous_background = current_background;
                this.orm.call('account.invoiceset',
                              'background_calculation_active',
                              [[this.model.root.resId]]
                    ).then((result) => {
                        current_background = result;
                        if (current_background ||
                            (!current_background && previous_background)) {
                            this.model.load();
                        }
                    });
            }, INTERVAL);
        }
    }

};

registry.category('views').add('invoiceset_view_form', {
    ...formView,
    Controller: MassiveInvoicingFormController,
});
