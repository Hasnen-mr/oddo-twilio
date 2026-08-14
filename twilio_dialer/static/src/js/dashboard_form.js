/** @odoo-module **/

import { onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { TwilioOnboardingWizard } from "@twilio_dialer/js/onboarding_wizard";
import { deviceManager } from "@twilio_dialer/js/device_manager";

function scrollTwilioDashboardToTop() {
    const selectors = [
        ".o_action_manager .o_content",
        ".o_content",
        ".o_form_view",
        ".o_form_renderer",
    ];
    for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el) {
            el.scrollTop = 0;
        }
    }
    window.scrollTo(0, 0);
}

export class TwilioDashboardFormController extends FormController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.dialer = useService("twilio_dialer");
        this._onboardingShown = false;

        onMounted(() => {
            scrollTwilioDashboardToTop();
            requestAnimationFrame(scrollTwilioDashboardToTop);
            setTimeout(scrollTwilioDashboardToTop, 50);
            setTimeout(scrollTwilioDashboardToTop, 200);
            // Open after the form paints so a wizard error cannot blank the view.
            setTimeout(() => this._maybeOpenOnboarding(), 100);
        });
    }

    _maybeOpenOnboarding() {
        if (this._onboardingShown) {
            return;
        }
        const data = this.model?.root?.data;
        if (!data || data.connection_configured) {
            return;
        }
        this._onboardingShown = true;
        let connected = false;
        try {
            this.dialog.add(
                TwilioOnboardingWizard,
                {
                    onConnected: () => {
                        connected = true;
                    },
                    onOpenDialer: async () => {
                        const ready = await deviceManager.ensureRegistered({
                            regenerate: true,
                            timeoutMs: 45000,
                        });
                        if (ready) {
                            this.dialer.open();
                        }
                        return ready;
                    },
                },
                {
                    onClose: () => {
                        if (connected) {
                            this.action.doAction("twilio_dialer.action_twilio_dashboard", {
                                stackPosition: "replaceCurrentAction",
                            });
                        }
                    },
                }
            );
        } catch (err) {
            console.error("[TwilioDashboard] Failed to open onboarding wizard:", err);
            this._onboardingShown = false;
        }
    }
}

registry.category("views").add("twilio_dashboard_form", {
    ...formView,
    Controller: TwilioDashboardFormController,
});
