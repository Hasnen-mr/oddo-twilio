/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { normalizePhoneNumber } from "./phone_utils";

const dialerState = reactive({
    isOpen: false,
    phone: "",
    fromNumber: "",
    partnerId: null,
    partnerName: "",
    requestId: 0,
});

export const dialerService = {
    dependencies: [],
    start() {
        return {
            get state() {
                return dialerState;
            },
            open({ phone = "", fromNumber = "", partnerId = null, partnerName = "" } = {}) {
                dialerState.phone = normalizePhoneNumber(phone);
                dialerState.fromNumber = fromNumber || "";
                dialerState.partnerId = partnerId || null;
                dialerState.partnerName = partnerName || "";
                dialerState.requestId += 1;
                dialerState.isOpen = true;
            },
            close() {
                dialerState.isOpen = false;
            },
            toggle() {
                dialerState.isOpen = !dialerState.isOpen;
            },
        };
    },
};

registry.category("services").add("twilio_dialer", dialerService);

registry.category("actions").add("twilio_dialer.open_dialer", (env, action) => {
    const params = action.params || {};
    env.services.twilio_dialer.open({
        phone: params.phone || "",
        fromNumber: params.from_number || "",
        partnerId: params.partner_id || null,
        partnerName: params.partner_name || "",
    });
    return Promise.resolve();
});
