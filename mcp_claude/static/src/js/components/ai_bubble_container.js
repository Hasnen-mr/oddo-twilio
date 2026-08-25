/** @odoo-module **/

import { AIBubbleTrigger } from "@mcp_claude/js/components/ai_bubble_trigger";
import { AIChatWindow } from "@mcp_claude/js/components/ai_chat_window";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class AIBubbleContainer extends Component {
    static template = "mcp_claude.AIBubbleContainer";
    static components = { AIBubbleTrigger, AIChatWindow };

    setup() {
        const activeTab = localStorage.getItem("mcp_active_tab") || "dashboard";
        this.state = useState({
            isOpen: false,
            isHiddenOnClaude: activeTab === "claude",
            isBubbleDismissed: false,
            isBubbleDisabled: localStorage.getItem("mcp_bubble_enabled") === "false",
            isEmailVerified: true,
            showGlobalVerifyModal: false,
            globalUserEmail: "",
            globalOtp: "",
            globalSendingOtp: false,
            globalVerifyingOtp: false,
            globalOtpSent: false,
            globalOtpError: "",
            globalOtpSuccess: "",
        });

        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this._onTabChange = (ev) => {
            const currentTab = (ev.detail && ev.detail.tab) || localStorage.getItem("mcp_active_tab");
            this.state.isHiddenOnClaude = (currentTab === "claude");
            if (this.state.isHiddenOnClaude) {
                this.state.isOpen = false;
            }
        };

        this._onToggleWindow = (ev) => {
            if (this.state.isHiddenOnClaude) return;
            this.state.isOpen = !this.state.isOpen;
        };

        this._onCloseWindow = (ev) => {
            this.state.isOpen = false;
        };

        this._onClickOutside = (ev) => {
            if (!this.state.isOpen) return;
            const target = ev.target;
            if (!target) return;

            const insideChatWindow = target.closest && target.closest(".o_mcp_ai_chat_window");
            const insideBubbleTrigger = target.closest && target.closest(".o_mcp_ai_bubble_trigger");
            const insideSystrayBtn = target.closest && target.closest(".o_mcp_ai_systray_btn");

            if (!insideChatWindow && !insideBubbleTrigger && !insideSystrayBtn) {
                this.state.isOpen = false;
            }
        };

        this._onKeyDown = (ev) => {
            if (this.state.isOpen && (ev.key === "Escape" || ev.key === "Esc")) {
                this.state.isOpen = false;
            }
        };

        this._onRestoreBubble = () => {
            this.state.isBubbleDismissed = false;
        };

        this._onBubbleSettingChange = (ev) => {
            if (ev.detail && ev.detail.enabled !== undefined) {
                this.state.isBubbleDisabled = !ev.detail.enabled;
            } else {
                this.state.isBubbleDisabled = (localStorage.getItem("mcp_bubble_enabled") === "false");
            }
        };

        this._checkGlobalVerification = async () => {
            try {
                const res = await this.orm.call("mcp.tool", "get_email_verification_status", []);
                if (res) {
                    this.state.isEmailVerified = Boolean(res.verified);
                    this.state.globalUserEmail = res.email || "";
                    if (!this.state.isEmailVerified) {
                        this._scheduleGlobalNag();
                    }
                }
            } catch (e) {
                // Ignore background check errors
            }
        };

        this._scheduleGlobalNag = () => {
            if (this._globalNagTimer) clearTimeout(this._globalNagTimer);
            if (!this.state.isEmailVerified) {
                this._globalNagTimer = setTimeout(() => {
                    const isInControlCenter = window.location.href.includes("mcp.control.center") || document.querySelector(".mcp-control-center");
                    if (!this.state.isEmailVerified && !isInControlCenter) {
                        this.state.showGlobalVerifyModal = true;
                        this.state.globalOtpError = "";
                        this.state.globalOtpSuccess = "";
                        if (!this.state.globalOtpSent && this.state.globalUserEmail) {
                            this.sendGlobalOtp(false);
                        }
                    }
                }, 10000); // 10 seconds
            }
        };

        window.addEventListener("mcp_tab_changed", this._onTabChange);
        window.addEventListener("toggle_mcp_ai_window", this._onToggleWindow);
        window.addEventListener("close_mcp_ai_window", this._onCloseWindow);
        window.addEventListener("restore_mcp_ai_bubble", this._onRestoreBubble);
        window.addEventListener("mcp_bubble_setting_changed", this._onBubbleSettingChange);
        document.addEventListener("pointerdown", this._onClickOutside);
        document.addEventListener("keydown", this._onKeyDown);

        onWillStart(async () => {
            await this._checkGlobalVerification();
        });

        onWillUnmount(() => {
            if (this._globalNagTimer) clearTimeout(this._globalNagTimer);
            window.removeEventListener("mcp_tab_changed", this._onTabChange);
            window.removeEventListener("toggle_mcp_ai_window", this._onToggleWindow);
            window.removeEventListener("close_mcp_ai_window", this._onCloseWindow);
            window.removeEventListener("restore_mcp_ai_bubble", this._onRestoreBubble);
            window.removeEventListener("mcp_bubble_setting_changed", this._onBubbleSettingChange);
            document.removeEventListener("pointerdown", this._onClickOutside);
            document.removeEventListener("keydown", this._onKeyDown);
        });
    }

    dismissBubble(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.state.isBubbleDismissed = true;
        this.state.isOpen = false;
    }

    toggleWindow() {
        if (this.state.isHiddenOnClaude) return;
        this.state.isOpen = !this.state.isOpen;
    }

    closeWindow() {
        this.state.isOpen = false;
    }

    closeGlobalVerifyModal() {
        this.state.showGlobalVerifyModal = false;
        if (!this.state.isEmailVerified) {
            this._scheduleGlobalNag();
        }
    }

    async sendGlobalOtp(isResend = false) {
        if (this.state.globalSendingOtp) return;
        const email = (this.state.globalUserEmail || "").trim();
        if (!email) {
            this.state.globalOtpError = "Please enter a valid email address.";
            return;
        }
        this.state.globalSendingOtp = true;
        this.state.globalOtpError = "";
        this.state.globalOtpSuccess = "";
        try {
            const res = await this.orm.call("mcp.tool", "send_registration_otp", [], { email: email });
            if (res && res.success) {
                this.state.globalOtpSent = true;
                this.state.globalOtpSuccess = isResend ? "Verification code resent!" : "Verification code sent to your email!";
            } else {
                this.state.globalOtpError = (res && res.error) || "Could not send verification code.";
            }
        } catch (e) {
            this.state.globalOtpError = (e && e.data && e.data.message) || e.message || "Failed to send code.";
        } finally {
            this.state.globalSendingOtp = false;
        }
    }

    async verifyGlobalOtp() {
        if (this.state.globalVerifyingOtp) return;
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
                if (this._globalNagTimer) clearTimeout(this._globalNagTimer);
                this.notification.add("Email verified successfully! Setup complete.", { type: "success" });
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
