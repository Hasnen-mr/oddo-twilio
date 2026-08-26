/** @odoo-module **/

import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { formatChar } from "@web/views/fields/formatters";

export class PasswordToggleField extends CharField {
    static template = "twilio_dialer.PasswordToggleField";

    setup() {
        super.setup();
        this.revealState = useState({ visible: false });
    }

    get inputType() {
        return this.revealState.visible ? "text" : "password";
    }

    get eyeIcon() {
        return this.revealState.visible ? "fa-eye-slash" : "fa-eye";
    }

    get eyeTitle() {
        return this.revealState.visible ? _t("Hide") : _t("Show");
    }

    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (this.revealState.visible) {
            return value || "";
        }
        return formatChar(value, { isPassword: true });
    }

    toggleVisibility(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.revealState.visible = !this.revealState.visible;
    }
}

export const passwordToggleField = {
    ...charField,
    component: PasswordToggleField,
    displayName: _t("Password (toggle)"),
    extractProps: (fieldInfo, dynamicInfo) => {
        const props = charField.extractProps(fieldInfo, dynamicInfo);
        props.isPassword = true;
        return props;
    },
};

registry.category("fields").add("password_toggle", passwordToggleField);
