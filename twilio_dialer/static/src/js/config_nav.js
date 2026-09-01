/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { BillingDashboard } from "@twilio_dialer/js/billing";
import { NumberAllocationPanel } from "@twilio_dialer/js/number_allocation";
import { setUiField } from "@twilio_dialer/js/settings_ui_field";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const SECTIONS = [
    { id: "account", label: _t("Account Settings"), icon: "fa-key" },
    { id: "call", label: _t("Call Settings"), icon: "fa-phone" },
    { id: "allocation", label: _t("My Team"), icon: "fa-users" },
    { id: "ai", label: _t("AI Settings"), icon: "fa-magic" },
    { id: "billing", label: _t("Billing"), icon: "fa-credit-card" },
];

export class TwilioConfigNav extends Component {
    static template = "twilio_dialer.TwilioConfigNav";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
        this.rootRef = useRef("root");
        this._syncingSection = false;
        this._wasConnected = null;

        onMounted(() => {
            this._applyShellLayout();
            this._applyDefaultSection();
            this._wasConnected = this.isConnected;
        });
        onWillUnmount(() => this._clearShellLayout());

        useEffect(
            () => {
                const connected = this.isConnected;
                if (this._wasConnected === null) {
                    this._wasConnected = connected;
                    return;
                }
                if (connected !== this._wasConnected) {
                    this._wasConnected = connected;
                    this._applyDefaultSection();
                }
            },
            () => [
                this.props.record.data.twilio_is_connected,
                this.props.record.data.twilio_api_key_sid,
                this.props.record.data.twilio_application_sid,
            ]
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
        const ctxSection = this.props.record.context?.active_section || this.props.record.context?.default_active_section;
        return this.props.record.data.twilio_config_section || ctxSection || "account";
    }

    get isConnected() {
        const data = this.props.record.data;
        return !!(
            data.twilio_is_connected ||
            (data.twilio_api_key_sid && data.twilio_application_sid)
        );
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
        this._setConfigSection(section.id);
    }

    backToDashboard() {
        const record = this.props.record;
        if (record && !this._hasRealPendingEdits(record)) {
            record.dirty = false;
        }
        const dashAction = "twilio_dialer.action_twilio_dashboard";
        this.action.doAction(dashAction);
    }

    _setConfigSection(sectionId) {
        const record = this.props.record;
        const wasDirty = record.dirty;
        setUiField(record, "twilio_config_section", sectionId);
        this._applySectionAttr(sectionId);
        const clearSpurious = () => {
            if (!wasDirty && record.dirty) {
                record.dirty = false;
            }
        };
        queueMicrotask(clearSpurious);
        setTimeout(clearSpurious, 0);
        setTimeout(clearSpurious, 120);
    }

    _hasRealPendingEdits(record) {
        return !!record.dirty;
    }

    _applySectionAttr(sectionId) {
        const appBlock = this._findAppBlock();
        if (!appBlock) {
            return;
        }
        appBlock.setAttribute("data-twilio-section", sectionId || "account");
    }

    _applyDefaultSection() {
        if (this._syncingSection) {
            return;
        }
        const ctxSection = this.props.record.context?.active_section || this.props.record.context?.default_active_section;
        const current = this.props.record.data.twilio_config_section || ctxSection;
        const target = current || "account";
        this._syncingSection = true;
        try {
            if (this.props.record.data.twilio_config_section !== target) {
                this._setConfigSection(target);
            } else {
                this._applySectionAttr(target);
            }
        } finally {
            this._syncingSection = false;
        }
    }

    _findAppBlock() {
        return this.rootRef.el?.closest(".app_settings_block[data-key='twilio_dialer'], .app_settings_block[data-key='twilio_dialer_pro'], .app_settings_block") || null;
    }

    _applyShellLayout() {
        const appBlock = this._findAppBlock();
        if (!appBlock) {
            return;
        }
        appBlock.classList.add("o_twilio_cfg_shell");
        this._applySectionAttr(this.activeSection);
        const host =
            this.rootRef.el?.closest(".o_setting_box") ||
            this.rootRef.el?.closest(".o_settings_container") ||
            this.rootRef.el?.parentElement;
        if (host) {
            host.classList.add("o_twilio_cfg_nav_host");
        }

        // Hide outer multi-app Odoo settings sidebar and expand to full width
        const settingsTab = document.querySelector(".settings_tab");
        const settingsBody = document.querySelector(".settings");
        const settingsView = this.rootRef.el?.closest(".settings_form_view, .o_form_view, .o_settings_container");
        if (settingsTab) {
            settingsTab.classList.add("o_twilio_hide_outer_sidebar");
        }
        if (settingsBody) {
            settingsBody.classList.add("o_twilio_fullwidth_settings");
        }
        if (settingsView) {
            settingsView.classList.add("o_twilio_standalone_settings");
        }
    }

    _clearShellLayout() {
        const appBlock = this._findAppBlock();
        appBlock?.classList.remove("o_twilio_cfg_shell");
        document.querySelectorAll(".o_twilio_cfg_nav_host").forEach((el) => {
            el.classList.remove("o_twilio_cfg_nav_host");
        });
        document.querySelector(".settings_tab")?.classList.remove("o_twilio_hide_outer_sidebar");
        document.querySelector(".settings")?.classList.remove("o_twilio_fullwidth_settings");
        document.querySelectorAll(".o_twilio_standalone_settings").forEach((el) => {
            el.classList.remove("o_twilio_standalone_settings");
        });
    }
}

export const twilioConfigNav = {
    component: TwilioConfigNav,
    supportedTypes: ["selection", "char"],
};

registry.category("fields").add("twilio_config_nav", twilioConfigNav, { force: true });

export class TwilioAllocationPanel extends Component {
    static template = "twilio_dialer.TwilioAllocationPanel";
    static props = { ...standardFieldProps };
    static components = { NumberAllocationPanel };
}

export const twilioAllocationPanel = {
    component: TwilioAllocationPanel,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_allocation_panel", twilioAllocationPanel, { force: true });

export class TwilioBillingPanel extends Component {
    static template = "twilio_dialer.TwilioBillingPanel";
    static props = { ...standardFieldProps };
    static components = { BillingDashboard };
}

export const twilioBillingPanel = {
    component: TwilioBillingPanel,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_billing_panel", twilioBillingPanel, { force: true });
