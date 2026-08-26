/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const TOTAL_STEPS = 4;

export class TwilioOnboardingWizard extends Component {
    static template = "twilio_dialer.OnboardingWizard";
    static components = { Dialog };
    static props = {
        close: Function,
        onConnected: { type: Function, optional: true },
        onOpenDialer: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            step: 1,
            connecting: false,
            connected: false,
            registeringToken: false,
            tokenReady: false,
            accountSid: "",
            authToken: "",
            email: "",
            phone: "",
            allowIncomingCall: true,
            odooVersion: (session && session.server_version) || "",
            error: "",
        });

        this._canClose = false;

        onMounted(() => {
            document.body.classList.add("o_twilio_onboard_open");
            this._lockDismiss();
            this._prefillContact();
        });
        onWillUnmount(() => {
            document.body.classList.remove("o_twilio_onboard_open");
        });
    }

    _lockDismiss() {
        const dialogData = this.env.dialogData;
        if (!dialogData || dialogData._twilioOnboardLocked) {
            return;
        }
        dialogData._twilioOnboardLocked = true;
        const originalClose = dialogData.close.bind(dialogData);
        dialogData.close = () => {
            if (this._canClose) {
                originalClose();
            }
        };
        // Allow header X / Escape key to dismiss wizard cleanly
        dialogData.dismiss = async () => {
            this.dismissWizard();
        };
    }

    dismissWizard() {
        this._canClose = true;
        document.body.classList.remove("o_twilio_onboard_open");
        this.props.close();
    }

    _closeWizard() {
        this.dismissWizard();
    }

    get dialogTitle() {
        return _t("Get Started with Twilio Dialer");
    }

    get stepLabel() {
        return `Step ${this.state.step} of ${TOTAL_STEPS}`;
    }

    get canGoNext() {
        if (this.state.step === 3 && !this.state.connected) {
            return false;
        }
        return this.state.step < TOTAL_STEPS;
    }

    get canConnect() {
        return (
            !this.state.connecting &&
            !this.state.connected &&
            this.state.accountSid.trim() &&
            this.state.authToken.trim() &&
            this.state.email.trim()
        );
    }

    async _prefillContact() {
        try {
            if (session && session.uid) {
                const users = await this.orm.searchRead(
                    "res.users",
                    [["id", "=", session.uid]],
                    ["email", "login", "phone"],
                    { limit: 1 }
                );
                const user = users[0] || {};
                if (!this.state.email) {
                    this.state.email = user.email || user.login || "";
                }
                if (!this.state.phone) {
                    this.state.phone = user.phone || "";
                }
            }
        } catch (err) {
            console.warn("[TwilioOnboarding] Prefill contact failed:", err);
        }
        if (!this.state.odooVersion) {
            this.state.odooVersion = (session && session.server_version) || "";
        }
    }

    nextStep() {
        if (this.state.step < TOTAL_STEPS) {
            this.state.step += 1;
            this.state.error = "";
        }
    }

    prevStep() {
        if (this.state.step > 1 && !this.state.connecting) {
            this.state.step -= 1;
            this.state.error = "";
        }
    }

    async onConnect() {
        if (!this.canConnect) {
            return;
        }
        this.state.connecting = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "res.config.settings",
                "twilio_wizard_connect",
                [],
                {
                    account_sid: this.state.accountSid.trim(),
                    auth_token: this.state.authToken.trim(),
                    email: this.state.email.trim(),
                    phone: this.state.phone.trim(),
                    odoo_version: this.state.odooVersion.trim(),
                    allow_incoming: this.state.allowIncomingCall,
                }
            );
            if (result && result.success) {
                this.state.connected = true;
                this.state.step = 4;
                this.notification.add(
                    _t("Twilio connected successfully."),
                    { type: "success" }
                );
                if (this.props.onConnected) {
                    await this.props.onConnected(result);
                }
                await this.registerToken();
            } else {
                this.state.error = (result && result.error) || _t("Connection failed. Check your credentials.");
            }
        } catch (err) {
            const message =
                (err && err.data && err.data.message) ||
                (err && err.message) ||
                _t("Could not connect Twilio. Check your credentials.");
            this.state.error = message;
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.connecting = false;
        }
    }

    async registerToken() {
        if (this.state.registeringToken) {
            return;
        }
        this.state.registeringToken = true;
        this.state.error = "";
        try {
            let registered = false;
            if (this.props.onOpenDialer) {
                registered = await this.props.onOpenDialer();
            }
            if (registered) {
                this.state.tokenReady = true;
                this.state.error = "";
            } else {
                this.state.tokenReady = false;
                this.state.error = _t(
                    "Credentials were saved, but softphone token registration failed or timed out. Check your network connection or click Retry Registration."
                );
            }
        } catch (err) {
            this.state.tokenReady = false;
            this.state.error =
                (err && err.message) ||
                _t("Could not register softphone token. Please try again.");
        } finally {
            this.state.registeringToken = false;
        }
    }

    async openDialer() {
        if (this.state.tokenReady) {
            this.dismissWizard();
            return;
        }
        await this.registerToken();
        if (this.state.tokenReady) {
            this.dismissWizard();
        }
    }
}