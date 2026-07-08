/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { bus } from "@web/core/core";

const TWILIO_CALL_STARTED = "twilio_call_started";
const DEFAULT_GREETING_SCRIPT =
    "Hello! This is [Your Name] calling from [Company]. I'm following up on our recent conversation. Do you have a moment to talk?";

/**
 * CallInProgressScreen: Full-screen call UI shown when a Twilio call is initiated successfully.
 * Shows timer, number, script card, Mute/Dialpad buttons, End Call, and bottom nav.
 */
export class CallInProgressScreen extends Component {
    static template = "twilio_dialer.CallInProgressScreen";

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            visible: false,
            toNumber: "",
            countryCode: "+91",
            duration: 0,
            muted: false,
            dialpadOpen: false,
            greetingScript: DEFAULT_GREETING_SCRIPT,
        });
        this.timerInterval = null;

        useBus(bus, TWILIO_CALL_STARTED, (payload) => {
            this.onCallStarted(payload);
        });

        onWillUnmount(() => {
            this.stopTimer();
        });
    }

    get fullNumber() {
        const { countryCode, toNumber } = this.state;
        const to = (toNumber || "").trim();
        const code = (countryCode || "").trim();
        if (!to) return code || "—";
        return code ? `${code}${to}` : to;
    }

    get formattedDuration() {
        const d = this.state.duration;
        const m = Math.floor(d / 60);
        const s = d % 60;
        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    onCallStarted(payload) {
        this.state.visible = true;
        this.state.toNumber = payload.toNumber || "";
        this.state.countryCode = payload.countryCode || "+91";
        this.state.duration = 0;
        this.state.muted = false;
        this.state.dialpadOpen = false;
        this.state.greetingScript = payload.greetingScript || DEFAULT_GREETING_SCRIPT;
        this.startTimer();
    }

    startTimer() {
        this.stopTimer();
        this.timerInterval = setInterval(() => {
            this.state.duration += 1;
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    endCall() {
        this.stopTimer();
        this.state.visible = false;
        // Existing hangup is phone-side; closing the UI here.
        // If a hangup RPC is added later, it can be called here.
    }

    toggleMute() {
        this.state.muted = !this.state.muted;
    }

    toggleDialpad() {
        this.state.dialpadOpen = !this.state.dialpadOpen;
    }

    openCallLog() {
        this.endCall();
        this.actionService.doAction("twilio_dialer.action_open_call_logs_direct");
    }

    openDialpad() {
        this.endCall();
        this.actionService.doAction("twilio_dialer.action_click_to_call_wizard");
    }

    openSms() {
        this.endCall();
        this.actionService.doAction("twilio_dialer.action_send_sms_wizard");
    }

    openSettings() {
        this.endCall();
        this.actionService.doAction("twilio_dialer.action_twilio_config");
    }
}

CallInProgressScreen.components = {};

// Capture last dialed number when Call button is clicked (before RPC)
let lastCallPayload = null;

function triggerCallStartedIfPending() {
    if (lastCallPayload) {
        bus.trigger(TWILIO_CALL_STARTED, { ...lastCallPayload });
        lastCallPayload = null;
    }
}

function captureCallFormData() {
    const dialer = document.querySelector("[data-twilio-dialer]");
    const form = dialer || document.querySelector(".o_form_view, .dialer-container") || document.querySelector("form");
    const root = form || document.body;
    const toInput = root.querySelector('input[name="to_number"]') ||
        root.querySelector('input[id*="to_number"]') ||
        root.querySelector(".dialer-container input[type=\"text\"]") ||
        (dialer && dialer.querySelector('input[placeholder*="1234567890"]')) ||
        (root.querySelector(".number-display + * input")) ||
        Array.from(root.querySelectorAll("input")).find((i) => (i.placeholder || "").includes("1234567890") || (i.placeholder || "").includes("number"));
    const countrySelect = root.querySelector('select[name="country_code"]') ||
        root.querySelector('select[id*="country_code"]') ||
        root.querySelector(".dialer-container select") ||
        (dialer && dialer.querySelector("select"));
    const toNumber = toInput ? (toInput.value || "").trim() : "";
    const countryCode = countrySelect ? (countrySelect.value || "+91") : "+91";
    lastCallPayload = { toNumber, countryCode };
}

function checkAndTriggerCallStarted() {
    if (!lastCallPayload) return;
    const bodyText = (document.body && document.body.innerText) || "";
    const lower = bodyText.toLowerCase();
    if (lower.includes("call initiated") || lower.includes("your phone will ring shortly")) {
        triggerCallStartedIfPending();
        return true;
    }
    return false;
}

function initCallStartedTrigger() {
    document.body.addEventListener(
        "click",
        (e) => {
            const callBtn = e.target.closest("#call-btn, .twilio-call-initiate-btn, button[name='action_initiate_call']");
            if (callBtn) {
                captureCallFormData();
                const pollMs = 400;
                const pollMax = 6000;
                let elapsed = 0;
                const poll = () => {
                    if (checkAndTriggerCallStarted() || elapsed >= pollMax) return;
                    elapsed += pollMs;
                    setTimeout(poll, pollMs);
                };
                setTimeout(poll, pollMs);
            }
        },
        true
    );

    const observer = new MutationObserver(() => {
        checkAndTriggerCallStarted();
    });

    function observeTarget(target) {
        if (target && !target._twilioObserved) {
            target._twilioObserved = true;
            observer.observe(target, { childList: true, subtree: true });
        }
    }
    const notifContainer = document.querySelector(".o_notification_manager, .o_notification, [class*='notification'], [class*='Notification']");
    observeTarget(notifContainer || document.body);
    setTimeout(() => {
        observeTarget(document.querySelector(".o_notification_manager, .o_notification, [class*='notification'], [class*='Notification']") || document.body);
    }, 1000);
}

// Run when the module loads so that we capture Call button clicks and success notifications
if (typeof document !== "undefined" && document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCallStartedTrigger);
} else {
    initCallStartedTrigger();
}

export { TWILIO_CALL_STARTED };

const webClientComponents = registry.category("webclient_components");
webClientComponents.add("TwilioCallInProgressScreen", {
    Component: CallInProgressScreen,
    props: {},
});
