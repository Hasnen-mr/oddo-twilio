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
    autoDialerId: null,
    queueLineId: null,
    queueName: "",
    queuePosition: "",
    queueAttempts: 0,
    queueNotes: "",
    queueStatus: "",
});

export const dialerService = {
    dependencies: [],
    start() {
        return {
            get state() {
                return dialerState;
            },
            open({
                phone = "",
                fromNumber = "",
                partnerId = null,
                partnerName = "",
                autoDialerId = null,
                queueLineId = null,
                queueName = "",
                queuePosition = "",
                queueAttempts = 0,
                queueNotes = "",
                queueStatus = "",
            } = {}) {
                dialerState.phone = normalizePhoneNumber(phone);
                dialerState.fromNumber = fromNumber || "";
                dialerState.partnerId = partnerId || null;
                dialerState.partnerName = partnerName || "";
                dialerState.autoDialerId = autoDialerId || null;
                dialerState.queueLineId = queueLineId || null;
                dialerState.queueName = queueName || "";
                dialerState.queuePosition = queuePosition || "";
                dialerState.queueAttempts = queueAttempts || 0;
                dialerState.queueNotes = queueNotes || "";
                dialerState.queueStatus = queueStatus || "";
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
        autoDialerId: params.auto_dialer_id || null,
        queueLineId: params.queue_line_id || null,
        queueName: params.queue_name || "",
        queuePosition: params.queue_position || "",
        queueAttempts: params.queue_attempts || 0,
        queueNotes: params.queue_notes || "",
        queueStatus: params.queue_status || "",
    });
    return Promise.resolve();
});
