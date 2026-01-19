/** @odoo-module **/

import {registry} from "@web/core/registry";
import {FormController} from "@web/views/form/form_controller";
import {formView} from "@web/views/form/form_view";
import {useService} from "@web/core/utils/hooks";

const INTERVAL = 2000;

export class MassiveInvoicingFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this._previousBackground = false;
        this._currentBackground = false;
        this._refreshInterval = false;

        this._startInterval(this.props.resId);
    }

    _startInterval(resId) {
        this._clearInterval();
        if (!resId) {
            return;
        }

        this._intervalId = setInterval(async () => {
            this._previousBackground = this._currentBackground;
            this._currentBackground = await this.orm.call(
                "account.invoiceset",
                "background_calculation_active",
                [[resId]]
            );

            if (
                this._currentBackground ||
                (!this._currentBackground && this._previousBackground)
            ) {
                this.model.load();
            }
        }, INTERVAL);
    }

    _clearInterval() {
        if (this._intervalId) {
            clearInterval(this._intervalId);
            this._intervalId = false;
        }
    }

    async beforeLeave() {
        await super.beforeLeave();
        this._clearInterval();
    }

    async onPagerUpdate({offset, resIds}) {
        await super.onPagerUpdate({offset, resIds});
        this._previousBackground = false;
        this._currentBackground = false;
        this._startInterval(resIds[offset]);
    }

    async deleteRecord() {
        await super.deleteRecord();
        this._refreshInterval = true;
    }

    updateURL() {
        super.updateURL();

        if (this._refreshInterval) {
            this._refreshInterval = false;
            this._previousBackground = false;
            this._currentBackground = false;
            this._startInterval(this.model.root.resId);
        }
    }
}

registry.category("views").add("invoiceset_view_form", {
    ...formView,
    Controller: MassiveInvoicingFormController,
});
