/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { deviceManager } from "@twilio_dialer_pro/js/device_manager";
import { normalizePhoneNumber } from "@twilio_dialer_pro/js/phone_utils";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

const dialerState = reactive({
    isOpen: false,
    phone: "",
    fromNumber: "",
    partnerId: null,
    partnerName: "",
    resModel: null,
    resId: null,
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
    start(env) {
        // Initialize DeviceManager once globally when the Odoo web client loads
        deviceManager.initialize().catch((err) => {
            console.error("[dialerService] DeviceManager global initialize failed:", err);
        });

        // Automatically open the dialer popup when an incoming call arrives
        deviceManager.onIncomingCall((call, fromNumber, callSid, toNumber) => {
            dialerState.phone = fromNumber || "";
            dialerState.fromNumber = (toNumber && !toNumber.startsWith("client:") && !toNumber.startsWith("id_odoo_")) ? toNumber : "";
            dialerState.resModel = null;
            dialerState.resId = null;
            dialerState.autoDialerId = null;
            dialerState.queueLineId = null;
            dialerState.requestId += 1;
            dialerState.isOpen = true;
        });

        // Cleanup listener: Ensure Twilio WebSocket connections & Device instance are cleanly
        // un-registered and destroyed when user logs out, closes browser tab, or unloads window.
        const cleanupDevice = () => {
            try {
                deviceManager.destroy();
            } catch (err) {
                console.error("[dialerService] Error during deviceManager cleanup:", err);
            }
        };

        // Real-time Disconnect Listener: Reset dialer and destroy Twilio device when connection is removed
        if (env.services.bus_service) {
            env.services.bus_service.subscribe("twilio_connection_disconnected", () => {
                try {
                    deviceManager.destroy();
                } catch (e) {
                    console.warn("[dialerService] Error destroying device on disconnect:", e);
                }
                dialerState.isOpen = false;
                dialerState.phone = "";
                dialerState.fromNumber = "";
                dialerState.partnerId = null;
                dialerState.partnerName = "";
                dialerState.resModel = null;
                dialerState.resId = null;
                dialerState.autoDialerId = null;
                dialerState.queueLineId = null;
                dialerState.requestId += 1;
            });

            env.services.bus_service.subscribe("twilio_number_allocation_updated", async (payload) => {
                try {
                    const res = await rpc("/twilio_dialer/phone_number");
                    if (res && res.phone_numbers) {
                        deviceManager.setAllowedNumbers(res.phone_numbers);
                    }
                } catch (err) {
                    console.warn("[dialerService] Failed to refresh allocations on bus update:", err);
                }
            });
        }

        window.addEventListener("pagehide", cleanupDevice);
        window.addEventListener("beforeunload", cleanupDevice);

        return {
            get state() {
                return dialerState;
            },
            open({
                phone = "",
                fromNumber = "",
                partnerId = null,
                partnerName = "",
                resModel = null,
                resId = null,
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
                dialerState.resModel = resModel || null;
                dialerState.resId = resId || null;
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
            openTroubleshooter() {
                dialerState.openTroubleshooter = true;
                dialerState.requestId += 1;
                dialerState.isOpen = true;
            },
        };
    },
};

registry.category("services").add("twilio_dialer", dialerService, { force: true });

function _handleOpenDialerAction(env, action) {
    const params = (action && action.params) || {};
    const service = env.services.twilio_dialer;
    if (service) {
        service.open({
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
    }
}

const dialerActionTags = [
    "twilio_dialer_pro.open_dialer",
    "twilio_dialer_pro.open_dialer",
    "open_dialer",
    "action_twilio_dialer_open",
    "action_twilio_open_phone",
];
for (const tag of dialerActionTags) {
    registry.category("actions").add(tag, _handleOpenDialerAction, { force: true });
}
