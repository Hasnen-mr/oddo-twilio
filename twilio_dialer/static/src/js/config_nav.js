/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { BillingDashboard } from "./billing";

const SECTIONS = [
    { id: "call", label: _t("Call Settings"), icon: "fa-phone" },
    { id: "ai", label: _t("AI Settings"), icon: "fa-magic" },
    { id: "account", label: _t("Account Setting"), icon: "fa-key" },
    { id: "billing", label: _t("Billing"), icon: "fa-credit-card" },
];

export class TwilioConfigNav extends Component {
    static template = "twilio_dialer.TwilioConfigNav";
    static props = { ...standardFieldProps };

    setup() {
        this.rootRef = useRef("root");
        this._syncingSection = false;

        onMounted(() => {
            this._applyShellLayout();
            this._syncDefaultSection();
        });
        onWillUnmount(() => this._clearShellLayout());

        useEffect(
            () => {
                this._syncDefaultSection();
            },
            () => [this.props.record.data.twilio_is_connected]
        );
    }

    get sections() {
        if (!this.isConnected) {
            return SECTIONS.filter((section) => section.id === "account");
        }
        return SECTIONS;
    }

    get activeSection() {
        if (!this.isConnected) {
            return "account";
        }
        return this.props.record.data.twilio_config_section || "call";
    }

    get isConnected() {
        return !!this.props.record.data.twilio_is_connected;
    }

    isActive(section) {
        return this.activeSection === section.id;
    }

    async selectSection(section) {
        if (this.isActive(section)) {
            return;
        }
        if (!this.isConnected && section.id !== "account") {
            return;
        }
        await this.props.record.update({ twilio_config_section: section.id });
    }

    async _syncDefaultSection() {
        if (this._syncingSection) {
            return;
        }
        const connected = this.isConnected;
        const current = this.props.record.data.twilio_config_section;
        const target = connected
            ? current && ["call", "ai", "account", "billing"].includes(current)
                ? null
                : "call"
            : current === "account"
                ? null
                : "account";

        if (!target) {
            return;
        }
        this._syncingSection = true;
        try {
            await this.props.record.update({ twilio_config_section: target });
        } finally {
            this._syncingSection = false;
        }
    }

    _findAppBlock() {
        return this.rootRef.el?.closest(".app_settings_block[data-key='twilio_dialer']") || null;
    }

    _applyShellLayout() {
        const appBlock = this._findAppBlock();
        if (!appBlock) {
            return;
        }
        appBlock.classList.add("o_twilio_cfg_shell");
        const host =
            this.rootRef.el.closest(".o_setting_box") ||
            this.rootRef.el.closest(".o_settings_container") ||
            this.rootRef.el.parentElement;
        if (host) {
            host.classList.add("o_twilio_cfg_nav_host");
        }
    }

    _clearShellLayout() {
        const appBlock = this._findAppBlock();
        appBlock?.classList.remove("o_twilio_cfg_shell");
        document.querySelectorAll(".o_twilio_cfg_nav_host").forEach((el) => {
            el.classList.remove("o_twilio_cfg_nav_host");
        });
    }
}

export const twilioConfigNav = {
    component: TwilioConfigNav,
    supportedTypes: ["selection", "char"],
};

registry.category("fields").add("twilio_config_nav", twilioConfigNav);

export class TwilioBillingPanel extends Component {
    static template = "twilio_dialer.TwilioBillingPanel";
    static props = { ...standardFieldProps };
    static components = { BillingDashboard };
}

export const twilioBillingPanel = {
    component: TwilioBillingPanel,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_billing_panel", twilioBillingPanel);
