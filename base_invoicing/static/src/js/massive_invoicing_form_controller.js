/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount, useEffect } from "@odoo/owl";

const INTERVAL = 2000;

export class MassiveInvoicingFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");

        this._previousBackground = false;
        this._currentBackground = false;
        this._intervalId = false;

        const getResId = () => this.model?.root?.resId || this.props?.resId;

        useEffect(
            () => {
                const resId = getResId();
                this._startInterval(resId);
                return () => this._clearInterval();
            },
            () => [getResId()]
        );

        onWillUnmount(() => this._clearInterval());
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

            if (this._currentBackground || (!this._currentBackground && this._previousBackground)) {
                // v18: según versión, una de estas 2 existe.
                if (this.model?.load) {
                    await this.model.load();
                } else if (this.model?.root?.load) {
                    await this.model.root.load();
                }
            }
        }, INTERVAL);
    }

    _clearInterval() {
        if (this._intervalId) {
            clearInterval(this._intervalId);
            this._intervalId = false;
        }
    }
}

registry.category("views").add("invoiceset_view_form", {
    ...formView,
    Controller: MassiveInvoicingFormController,
});
