/** @odoo-module **/

import { onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { TwilioOnboardingWizard } from "@twilio_dialer/js/onboarding_wizard";
import { TwilioHelpDialog } from "@twilio_dialer/js/help_dialog";
import { deviceManager } from "@twilio_dialer/js/device_manager";

function scrollTwilioDashboardToTop() {
    const header = document.querySelector(".o_twilio_dash_header");
    if (header && typeof header.scrollIntoView === "function") {
        try {
            header.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
        } catch (e) {
            header.scrollIntoView(true);
        }
    }

    const selectors = [
        ".o_action_manager .o_content",
        ".o_content",
        ".o_form_view",
        ".o_form_renderer",
        ".o_form_sheet_bg",
        ".o_action_manager",
        ".o_web_client",
    ];
    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        elements.forEach((el) => {
            if (el && el.scrollTop !== 0) {
                el.scrollTop = 0;
            }
        });
    }
    if (window.scrollY !== 0 || window.pageYOffset !== 0) {
        window.scrollTo(0, 0);
    }
    if (document.documentElement && document.documentElement.scrollTop !== 0) {
        document.documentElement.scrollTop = 0;
    }
    if (document.body && document.body.scrollTop !== 0) {
        document.body.scrollTop = 0;
    }
}

export class TwilioDashboardFormController extends FormController {
    static template = "twilio_dialer.TwilioDashboardFormView";

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.dialer = useService("twilio_dialer");
        this.orm = useService("orm");
        this._onboardingShown = false;
        this._isWizardOpen = false;
        this._reopenTimer = null;
        this._isComponentMounted = true;

        // Help bubble state: resets on every mount/navigation
        this.helpState = useState({
            isBubbleHidden: false,
        });

        onMounted(() => {
            this._isComponentMounted = true;
            
            // Blur any lower element that may have received auto-focus from sub-lists
            if (document.activeElement && document.activeElement !== document.body) {
                const isInsideDashboard = document.activeElement.closest(".o_twilio_dashboard_shell");
                if (isInsideDashboard && document.activeElement.tagName !== "INPUT") {
                    document.activeElement.blur();
                }
            }

            scrollTwilioDashboardToTop();
            requestAnimationFrame(scrollTwilioDashboardToTop);
            [20, 50, 100, 200, 400, 700, 1200].forEach((delay) => {
                setTimeout(() => {
                    if (this._isComponentMounted) {
                        scrollTwilioDashboardToTop();
                    }
                }, delay);
            });

            // Open after the form paints so a wizard error cannot blank the view.
            setTimeout(() => this._maybeOpenOnboarding(), 100);
        });

        onWillUnmount(() => {
            this._isComponentMounted = false;
            if (this._reopenTimer) {
                clearTimeout(this._reopenTimer);
                this._reopenTimer = null;
            }
        });
    }

    async _checkSetupIncomplete() {
        const data = this.model?.root?.data;
        if (data && data.connection_configured) {
            return false;
        }
        if (data && data.id) {
            try {
                const records = await this.orm.read(
                    "twilio.dashboard",
                    [data.id],
                    ["connection_configured"]
                );
                if (records && records.length > 0) {
                    return !records[0].connection_configured;
                }
            } catch (err) {
                console.warn("[TwilioDashboard] Re-check setup status warning:", err);
            }
        }
        return !data || !data.connection_configured;
    }

    async _maybeOpenOnboarding() {
        if (this._isWizardOpen || !this._isComponentMounted) {
            return;
        }

        const isIncomplete = await this._checkSetupIncomplete();
        if (!isIncomplete) {
            console.log("[TwilioDashboard] Twilio setup is complete, keeping dashboard unobstructed.");
            return;
        }

        this._isWizardOpen = true;
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
                        this._isWizardOpen = false;
                        if (connected) {
                            this.action.doAction("twilio_dialer.action_twilio_dashboard", {
                                stackPosition: "replaceCurrentAction",
                            });
                        } else {
                            // User closed popup without completing setup: schedule 5-second re-check
                            this._scheduleReopenCheck();
                        }
                    },
                }
            );
        } catch (err) {
            console.error("[TwilioDashboard] Failed to open onboarding wizard:", err);
            this._isWizardOpen = false;
        }
    }

    _scheduleReopenCheck() {
        if (this._reopenTimer) {
            clearTimeout(this._reopenTimer);
        }
        console.log("[TwilioDashboard] Onboarding popup closed without setup completion. Scheduling 5-second re-check...");
        this._reopenTimer = setTimeout(async () => {
            if (!this._isComponentMounted || this._isWizardOpen) {
                return;
            }
            const isIncomplete = await this._checkSetupIncomplete();
            if (isIncomplete) {
                console.log("[TwilioDashboard] 5s timer: Setup still incomplete, re-opening onboarding popup.");
                this._maybeOpenOnboarding();
            } else {
                console.log("[TwilioDashboard] 5s timer: Setup completed, suppressing popup.");
            }
        }, 5000);
    }

    onOpenHelpDialog(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.dialog.add(
            TwilioHelpDialog,
            {
                onOpenDialer: () => this.dialer.open(),
                onOpenTroubleshooter: () => this.dialer.openTroubleshooter(),
                onOpenConfig: () => {
                    this.action.doAction("twilio_dialer.action_twilio_configuration_menu");
                },
            }
        );
    }

    onHideHelpBubble(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.helpState.isBubbleHidden = true;
    }
}

registry.category("views").add("twilio_dashboard_form", {
    ...formView,
    Controller: TwilioDashboardFormController,
});