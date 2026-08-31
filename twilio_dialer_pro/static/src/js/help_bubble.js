/** @odoo-module **/

import { session } from "@web/session";
import { Component, onMounted, onWillUnmount, reactive, useState } from "@odoo/owl";
import { TwilioHelpDialog } from "@twilio_dialer_pro/js/help_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TwilioHelpBubble extends Component {
    static template = "twilio_dialer_pro.TwilioHelpBubble";

    setup() {
        this.dialog = useService("dialog");
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.dialer = useService("twilio_dialer");

        this.state = useState({
            isVisible: false,
            isClosedForCurrentTab: false,
            lastActionKey: null,
        });

        this._checkTimer = null;

        onMounted(() => {
            this._updateVisibility();
            // Polling interval to detect action/controller changes across web client seamlessly
            this._checkTimer = setInterval(() => this._updateVisibility(), 300);
        });

        onWillUnmount(() => {
            if (this._checkTimer) {
                clearInterval(this._checkTimer);
                this._checkTimer = null;
            }
        });
    }

    _updateVisibility() {
        const currentController = this.actionService ? this.actionService.currentController : null;
        const currentApp = this.menuService ? this.menuService.getCurrentApp() : null;
        const action = currentController ? currentController.action : null;

                // Guard: Never show on portal, website, login, or non-backend web client
        const path = window.location.pathname || "";
        if (
            path.startsWith("/my") ||
            path.startsWith("/website") ||
            path.startsWith("/shop") ||
            path.startsWith("/slides") ||
            path.startsWith("/web/login") ||
            (session && (session.is_portal || session.is_public || session.is_internal_user === false)) ||
            !document.body.classList.contains("o_web_client")
        ) {
            this.state.isVisible = false;
            return;
        }

        let isTwilioModule = false;

        // 1. Check if current active menu/app is Twilio Calling System
        if (currentApp) {
            const xmlid = currentApp.xmlid || "";
            const webIcon = currentApp.webIcon || "";
            const name = currentApp.name || "";
            if (
                xmlid === "twilio_dialer_pro.menu_twilio_dialer_root" ||
                webIcon.includes("twilio_dialer") ||
                name.includes("Twilio")
            ) {
                isTwilioModule = true;
            }
        }

        // 2. Check current action model, xml_id, or tag
        if (action) {
            const resModel = action.res_model || "";
            const xmlId = action.xml_id || "";
            const tag = action.tag || "";
            const params = action.params || {};

            if (
                resModel.startsWith("twilio.") ||
                xmlId.startsWith("twilio_dialer_pro.") || xmlId.startsWith("twilio_dialer.") ||
                tag.startsWith("twilio_") ||
                (resModel === "res.config.settings" && params.setting_module === "twilio_dialer")
            ) {
                isTwilioModule = true;
            }
        }

        // 3. Fallback: Check if any twilio shell / container is present in the DOM
        if (!isTwilioModule) {
            const hasTwilioEl = document.querySelector(
                ".o_twilio_dashboard_shell, .o_twilio_sms_workspace_root, .o_twilio_config_container, .o_twilio_contact_us_container, .o_twilio_auto_dialer_container"
            );
            if (hasTwilioEl) {
                isTwilioModule = true;
            }
        }

        // 4. Track tab / screen navigation to reset closed state
        const actionKey = action
            ? (action.id || action.tag || action.xml_id || action.res_model || action.name)
            : (currentApp ? currentApp.id : null);

        if (actionKey && actionKey !== this.state.lastActionKey) {
            this.state.lastActionKey = actionKey;
            this.state.isClosedForCurrentTab = false; // Re-appears when changing tabs!
        }

        // 5. Update final reactive visibility
        this.state.isVisible = Boolean(isTwilioModule && !this.state.isClosedForCurrentTab);
    }

    onOpenHelpDialog(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.dialog.add(TwilioHelpDialog, {
            onOpenDialer: () => this.dialer.open(),
            onOpenTroubleshooter: () => this.dialer.openTroubleshooter(),
            onOpenConfig: () => {
                this.actionService.doAction("twilio_dialer_pro.action_twilio_configuration_menu");
            },
            onOpenAboutHelp: () => {
                this.actionService.doAction("twilio_dialer_pro.action_twilio_help");
            },
        });
    }

    onHideHelpBubble(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.state.isClosedForCurrentTab = true;
        this.state.isVisible = false;
    }
}

registry.category("main_components").add("TwilioHelpBubble", {
    Component: TwilioHelpBubble,
}, { force: true });