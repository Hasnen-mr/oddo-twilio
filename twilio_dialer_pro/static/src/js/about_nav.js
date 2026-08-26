/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { setUiField } from "@twilio_dialer_pro/js/settings_ui_field";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const SECTIONS = [
    { id: "overview", label: _t("About Module"), icon: "fa-info-circle" },
    { id: "help", label: _t("Help"), icon: "fa-life-ring" },
    { id: "terms", label: _t("Terms & Privacy"), icon: "fa-file-text-o" },
];

export class TwilioAboutNav extends Component {
    static template = "twilio_dialer_pro.TwilioAboutNav";
    static props = { ...standardFieldProps };

    setup() {
        this.rootRef = useRef("root");
        onMounted(() => this._applyShellLayout());
        onWillUnmount(() => this._clearShellLayout());
    }

    get sections() {
        return SECTIONS;
    }

    get activeSection() {
        return this.props.record.data.about_section || "overview";
    }

    isActive(section) {
        return this.activeSection === section.id;
    }

    selectSection(section) {
        if (this.isActive(section)) {
            return;
        }
        setUiField(this.props.record, "about_section", section.id);
    }

    _findShell() {
        return this.rootRef.el?.closest(".o_twilio_about_form") || null;
    }

    _applyShellLayout() {
        const shell = this._findShell();
        if (!shell) {
            return;
        }
        shell.classList.add("o_twilio_about_shell");
        const host =
            this.rootRef.el.closest(".o_cell") ||
            this.rootRef.el.closest(".o_wrap_field") ||
            this.rootRef.el.parentElement;
        if (host) {
            host.classList.add("o_twilio_about_nav_host");
        }
    }

    _clearShellLayout() {
        this._findShell()?.classList.remove("o_twilio_about_shell");
        document.querySelectorAll(".o_twilio_about_nav_host").forEach((el) => {
            el.classList.remove("o_twilio_about_nav_host");
        });
    }
}

export const twilioAboutNav = {
    component: TwilioAboutNav,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_about_nav", twilioAboutNav);
