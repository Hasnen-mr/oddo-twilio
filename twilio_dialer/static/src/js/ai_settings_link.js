/** @odoo-module **/

import { Component } from "@odoo/owl";
import { setUiField } from "@twilio_dialer/js/settings_ui_field";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Inline link that switches Configuration sidebar to AI Settings
 * without marking the settings form dirty.
 */
export class TwilioAiSettingsLink extends Component {
    static template = "twilio_dialer.TwilioAiSettingsLink";
    static props = {
        ...standardFieldProps,
        linkLabel: { type: String, optional: true },
    };

    get label() {
        return this.props.linkLabel || _t("Open AI Settings");
    }

    openAiSettings(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        setUiField(this.props.record, "twilio_config_section", "ai");
    }
}

export const twilioAiSettingsLink = {
    component: TwilioAiSettingsLink,
    supportedTypes: ["char", "boolean"],
    extractProps: ({ options }) => ({
        linkLabel: options?.label,
    }),
};

registry.category("fields").add("twilio_ai_settings_link", twilioAiSettingsLink);
