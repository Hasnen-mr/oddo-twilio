/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { AIChatWindow } from "./ai_chat_window";

export class AIBubbleTrigger extends Component {
    static template = "mcp_claude.AIBubbleTrigger";
    static props = {
        isOpen: Boolean,
        onClick: Function,
        onDismiss: Function,
    };
}

export class AIBubbleContainer extends Component {
    static template = "mcp_claude.AIBubbleContainer";
    static components = { AIChatWindow, AIBubbleTrigger };
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");

        this.state = useState({
            isOpen: false,
            isHiddenOnClaude: false,
            isBubbleDismissed: false,
            isBubbleDisabled: false,
            // Verification State
            isEmailVerified: true,
            showGlobalVerifyModal: false,
            globalUserName: "",
            globalUserEmail: "",
            globalUserPhone: "",
            globalOtpSent: false,
            globalOtp: "",
            globalSendingOtp: false,
            globalVerifyingOtp: false,
            globalOtpError: "",
            globalOtpSuccess: "",
        });

        this._nagInterval = null;

        onWillStart(async () => {
            await this.loadVerificationStatus();
        });

        onMounted(() => {
            this.startPeriodicPrompt();
        });

        this._onToggleWindow = () => {
            this.state.isOpen = !this.state.isOpen;
            this.state.isBubbleDismissed = false;
        };
        window.addEventListener("toggle_mcp_ai_window", this._onToggleWindow);

        onWillUnmount(() => {
            window.removeEventListener("toggle_mcp_ai_window", this._onToggleWindow);
            if (this._nagInterval) {
                clearInterval(this._nagInterval);
            }
        });
    }

    async loadVerificationStatus() {
        try {
            const res = await this.orm.call("mcp.tool", "get_email_verification_status", []);
            if (res) {
                this.state.isEmailVerified = Boolean(res.verified);
                this.state.globalUserEmail = res.email || "";
                this.state.globalUserPhone = res.phone || "";
                this.state.globalUserName = res.user_name || "";
            }
        } catch (e) {
            // Fallback gracefully
        }
    }

    startPeriodicPrompt() {
        if (this._nagInterval) clearInterval(this._nagInterval);
        // Check every 8 seconds if unverified
        this._nagInterval = setInterval(() => {
            if (!this.state.isEmailVerified && !this.state.showGlobalVerifyModal) {
                this.state.showGlobalVerifyModal = true;
            }
        }, 8000);

        // Initial prompt after 2 seconds if not verified
        if (!this.state.isEmailVerified) {
            setTimeout(() => {
                if (!this.state.isEmailVerified) {
                    this.state.showGlobalVerifyModal = true;
                }
            }, 2000);
        }
    }

    toggleWindow() {
        this.state.isOpen = !this.state.isOpen;
    }

    closeWindow() {
        this.state.isOpen = false;
    }

    dismissBubble() {
        this.state.isBubbleDismissed = true;
    }

    closeGlobalVerifyModal() {
        this.state.showGlobalVerifyModal = false;
    }

    async sendGlobalRegistrationData(isResend = false) {
        const email = (this.state.globalUserEmail || "").trim();
        const phone = (this.state.globalUserPhone || "").trim();
        const name = (this.state.globalUserName || "").trim();

        if (!email) {
            this.state.globalOtpError = "Please enter a valid email address.";
            return;
        }
        if (!phone && !isResend) {
            this.state.globalOtpError = "Please enter your phone number.";
            return;
        }

        this.state.globalSendingOtp = true;
        this.state.globalOtpError = "";
        this.state.globalOtpSuccess = "";

        try {
            const res = await this.orm.call("mcp.tool", "send_registration_otp", [], {
                email: email,
                first_name: name,
                phone: phone,
            });
            if (res && res.success) {
                this.state.globalOtpSent = true;
                this.state.globalOtpSuccess = res.message || "Verification code sent to your email.";
            } else {
                this.state.globalOtpError = (res && res.error) || "Failed to send code.";
            }
        } catch (e) {
            this.state.globalOtpError = (e && e.data && e.data.message) || e.message || "Failed to send verification email.";
        } finally {
            this.state.globalSendingOtp = false;
        }
    }

    changeGlobalRegistrationData() {
        this.state.globalOtpSent = false;
        this.state.globalOtp = "";
        this.state.globalOtpError = "";
        this.state.globalOtpSuccess = "";
    }

    async verifyGlobalOtp() {
        const email = (this.state.globalUserEmail || "").trim();
        const otp = (this.state.globalOtp || "").trim();
        if (!otp) {
            this.state.globalOtpError = "Please enter the 6-digit code.";
            return;
        }

        this.state.globalVerifyingOtp = true;
        this.state.globalOtpError = "";
        try {
            const res = await this.orm.call("mcp.tool", "verify_registration_otp", [], { email: email, otp: otp });
            if (res && res.success && res.verified) {
                this.state.isEmailVerified = true;
                this.state.showGlobalVerifyModal = false;
                if (this._nagInterval) clearInterval(this._nagInterval);
                this.notification.add("Email verified successfully! Registration complete.", { type: "success" });
            } else {
                this.state.globalOtpError = (res && res.error) || "Invalid or expired code.";
            }
        } catch (e) {
            this.state.globalOtpError = (e && e.data && e.data.message) || e.message || "Failed to verify code.";
        } finally {
            this.state.globalVerifyingOtp = false;
        }
    }

    onGlobalOtpKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.verifyGlobalOtp();
        }
    }
}

registry.category("main_components").add("AIBubbleContainer", {
    Component: AIBubbleContainer,
});
