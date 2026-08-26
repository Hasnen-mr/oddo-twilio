/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { getCachedCallSettings, setCachedCallSettings } from "@twilio_dialer_pro/js/call_settings_cache";
import { TwilioCredentialsHelpDialog } from "@twilio_dialer_pro/js/credentials_help_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const TOTAL_STEPS = 5;

export class TwilioOnboardingWizard extends Component {
    static template = "twilio_dialer_pro.OnboardingWizard";
    static components = { Dialog };
    static props = {
        close: Function,
        onConnected: { type: Function, optional: true },
        onOpenDialer: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            step: 1,
            connecting: false,
            connected: false,

            // Email verification states
            otp: "",
            sendingOtp: false,
            otpSent: false,
            verifyingOtp: false,
            emailVerified: false,
            otpError: "",
            otpSuccessMessage: "",
            isEditingEmail: false,
            newEmail: "",

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

        this._onKeyDown = (ev) => {
            if (ev.key === "Enter") {
                if (ev.target && ev.target.tagName === "TEXTAREA") {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();

                if (this.state.step < 3) {
                    this.nextStep();
                } else if (this.state.step === 3) {
                    if (this.canConnect) {
                        this.onConnect();
                    }
                } else if (this.state.step === 4) {
                    if (this.state.otp.trim() && !this.state.verifyingOtp) {
                        this.verifyOtp();
                    }
                } else if (this.state.step === 5) {
                    if (this.state.tokenReady) {
                        this.openDialer();
                    } else if (!this.state.registeringToken) {
                        this.registerToken();
                    }
                }
            }
        };

        onMounted(() => {
            document.body.classList.add("o_twilio_onboard_open");
            this._lockDismiss();
            this._prefillContact();
            window.addEventListener("keydown", this._onKeyDown, true);
        });
        onWillUnmount(() => {
            document.body.classList.remove("o_twilio_onboard_open");
            window.removeEventListener("keydown", this._onKeyDown, true);
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
        if (this.state.step === 4 && !this.state.emailVerified) {
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
        const cached = getCachedCallSettings();
        if (cached && cached.incoming && cached.incoming.allow !== undefined) {
            this.state.allowIncomingCall = Boolean(cached.incoming.allow);
        }
    }

    nextStep() {
        if (this.state.step < TOTAL_STEPS) {
            this.state.step += 1;
            this.state.error = "";
        }
    }

    prevStep() {
        if (this.state.step > 1 && !this.state.connecting && !this.state.verifyingOtp) {
            this.state.step -= 1;
            this.state.error = "";
        }
    }

    openCredentialsHelp() {
        this.dialog.add(TwilioCredentialsHelpDialog);
    }

    onCheckCredentials() {
        this.state.step = 3;
    }

    onResendOtp() {
        this.sendOtp(true);
    }

    startEditingEmail() {
        this.state.newEmail = this.state.email;
        this.state.isEditingEmail = true;
        this.state.otpError = "";
    }

    cancelEditingEmail() {
        this.state.isEditingEmail = false;
        this.state.newEmail = "";
    }

    async saveAndResendNewEmail() {
        const trimmed = (this.state.newEmail || "").trim();
        if (!trimmed || !trimmed.includes("@") || !trimmed.includes(".")) {
            this.state.otpError = _t("Please enter a valid email address.");
            return;
        }
        this.state.email = trimmed;
        this.state.isEditingEmail = false;
        this.state.otp = "";
        this.state.otpError = "";
        try {
            await this.orm.call(
                "res.config.settings",
                "twilio_update_contact_email",
                [],
                { email: trimmed }
            );
        } catch (e) {
            console.warn("Failed to persist updated email:", e);
        }
        await this.sendOtp(true);
    }

    async onToggleIncomingCall(ev) {
        const val = ev.target.checked;
        this.state.allowIncomingCall = val;
        try {
            await this.orm.call(
                "res.config.settings",
                "twilio_update_incoming_setting",
                [],
                { allow_incoming: val }
            );
            setCachedCallSettings({
                success: true,
                accountSid: this.state.accountSid,
                incoming: { allow: val },
            });
        } catch (e) {
            console.warn("Failed to sync incoming call setting:", e);
        }
    }

    onOtpKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.verifyOtp();
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
                    _t("Twilio credentials verified and phone numbers fetched."),
                    { type: "success" }
                );
                // Trigger sending OTP verification email
                await this.sendOtp();
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

    async sendOtp(isResend = false) {
        if (this.state.sendingOtp) {
            return;
        }
        const email = this.state.email.trim();
        const accountSid = this.state.accountSid.trim();
        if (!email || !accountSid) {
            this.state.otpError = _t("Email and Account SID are required for verification.");
            return;
        }
        this.state.sendingOtp = true;
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
        try {
            const result = await this.orm.call(
                "res.config.settings",
                "twilio_send_registration_otp",
                [],
                {
                    email: email,
                    account_sid: accountSid,
                }
            );
            if (result && result.success) {
                this.state.otpSent = true;
                this.state.otpSuccessMessage = isResend
                    ? _t("Verification code resent! Please check your email inbox.")
                    : _t("Verification code sent! Please check your email inbox.");
            } else {
                let err = (result && result.error) || _t("Could not send verification email. Please try again.");
                if (err.toLowerCase().includes("limit reached")) {
                    err = _t("Daily email limit reached (5 per email per day). You can use a code already sent to your inbox (active for 10 minutes), or try again tomorrow.");
                }
                this.state.otpError = err;
            }
        } catch (err) {
            let msg =
                (err && err.data && err.data.message) ||
                (err && err.message) ||
                _t("Could not send verification email. Please check your network.");
            if (msg.toLowerCase().includes("limit reached")) {
                msg = _t("Daily email limit reached (5 per email per day). You can use a code already sent to your inbox (active for 10 minutes), or try again tomorrow.");
            }
            this.state.otpError = msg;
        } finally {
            this.state.sendingOtp = false;
        }
    }

    async verifyOtp() {
        if (this.state.verifyingOtp) {
            return;
        }
        const email = this.state.email.trim();
        const accountSid = this.state.accountSid.trim();
        const otp = this.state.otp.trim();
        if (!otp) {
            this.state.otpError = _t("Please enter the 6-digit verification code sent to your email.");
            return;
        }
        this.state.verifyingOtp = true;
        this.state.otpError = "";
        try {
            const result = await this.orm.call(
                "res.config.settings",
                "twilio_verify_registration_otp",
                [],
                {
                    email: email,
                    account_sid: accountSid,
                    otp: otp,
                    allow_incoming: this.state.allowIncomingCall,
                }
            );
            if (result && result.success && result.verified) {
                this.state.emailVerified = true;
                this.state.otpError = "";
                setCachedCallSettings({
                    success: true,
                    accountSid: accountSid,
                    incoming: { allow: this.state.allowIncomingCall },
                });
                this.notification.add(
                    _t("Email verified successfully."),
                    { type: "success" }
                );
                this.state.step = 5;
                if (this.props.onConnected) {
                    await this.props.onConnected({ success: true });
                }
                await this.registerToken();
            } else {
                this.state.otpError = (result && result.error) || _t("Invalid or expired verification code. Please try again.");
            }
        } catch (err) {
            this.state.otpError =
                (err && err.data && err.data.message) ||
                (err && err.message) ||
                _t("Verification request failed. Please check the code and try again.");
        } finally {
            this.state.verifyingOtp = false;
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
                    "Credentials and email were verified, but softphone token registration failed or timed out. Check your network connection or click Retry Registration."
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