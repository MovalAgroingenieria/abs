/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount, useEffect } from "@odoo/owl";

const INTERVAL_IDLE = 2000;
const INTERVAL_CALCULATING = 400;  // Fast refresh for real-time progress

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

        const poll = async () => {
            this._previousBackground = this._currentBackground;

            this._currentBackground = await this.orm.call(
                "account.invoiceset",
                "background_calculation_active",
                [[resId]]
            );

            if (this._currentBackground || (!this._currentBackground && this._previousBackground)) {
                if (this.model?.load) {
                    await this.model.load();
                } else if (this.model?.root?.load) {
                    await this.model.root.load();
                }
            }

            const nextMs = this._currentBackground ? INTERVAL_CALCULATING : INTERVAL_IDLE;
            this._intervalId = setTimeout(poll, nextMs);
        };
        poll();
    }

    _clearInterval() {
        if (this._intervalId) {
            clearTimeout(this._intervalId);
            this._intervalId = false;
        }
    }
}

registry.category("views").add("invoiceset_view_form", {
    ...formView,
    Controller: MassiveInvoicingFormController,
});
