/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import * as phoneFieldModule from "@web/views/fields/phone/phone_field";
const PhoneField = phoneFieldModule.PhoneField;
const phoneField = phoneFieldModule.phoneField;
const formPhoneField = phoneFieldModule.formPhoneField;
import { TwilioSmsMessagingDialog } from "./sms_messaging_dialog";

// ── Shared call-button component ─────────────────────────────────────────────
//
// Used in two contexts:
//   1. Inline in a PhoneField (Contacts view) — receives { record, name }
//   2. Standalone field widget (Call Log form)  — receives { record, name }
//
// Both contexts pass the same props: the record object and the field name whose
// value holds the phone number to dial.

export class ContactCallButton extends Component {
    static template = "twilio_dialer.ContactCallButton";
    static props = {
        record: { type: Object },
        name: { type: String },
    };

    setup() {
        this.dialer = useService("twilio_dialer");
        this.notification = useService("notification");
    }

    get phone() {
        return this.props.record.data[this.props.name] || "";
    }

    openDialer() {
        if (!this.phone) {
            this.notification.add(_t("No phone number available to dial."), {
                type: "warning",
            });
            return;
        }
        this.dialer.open({
            phone: this.phone,
            partnerId: this.props.record.data.partner_id?.[0] || this.props.record.resId || null,
            partnerName: this.props.record.data.partner_id?.[1]
                || this.props.record.data.name
                || "",
        });
    }
}

// ── Inline usage: injected into PhoneField (Contacts, etc.) ──────────────────

patch(PhoneField, {
    components: {
        ...PhoneField.components,
        ContactCallButton,
    },
    props: {
        ...PhoneField.props,
        enableDialerCall: { type: Boolean, optional: true },
    },
    defaultProps: {
        ...PhoneField.defaultProps,
        enableDialerCall: false,
    },
});

const patchDescription = () => ({
    extractProps({ options }) {
        return {
            ...super.extractProps(...arguments),
            enableDialerCall: options.enable_dialer_call || false,
        };
    },
});

if (phoneField) {
    patch(phoneField, patchDescription());
}
if (formPhoneField) {
    patch(formPhoneField, patchDescription());
}

// ── Standalone usage: "twilio_call_button" field widget ──────────────────────
//
// Usage in an Odoo form view:
//   <field name="to_number" widget="twilio_call_button" readonly="1"/>
//
// This renders the phone number as plain text followed immediately by the same
// red circular call button — identical to the one on the Contacts page.

class TwilioCallButtonField extends Component {
    static template = "twilio_dialer.TwilioCallButtonField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.dialer = useService("twilio_dialer");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }

    get phone() {
        return this.props.record.data[this.props.name] || "";
    }

    openDialer() {
        if (!this.phone) {
            this.notification.add(_t("No phone number available to dial."), {
                type: "warning",
            });
            return;
        }
        this.dialer.open({
            phone: this.phone,
            partnerId: this.props.record.data.partner_id?.[0] || null,
            partnerName: this.props.record.data.partner_id?.[1] || "",
        });
    }

    openSms() {
        if (!this.phone) {
            this.notification.add(_t("No phone number available to send SMS."), {
                type: "warning",
            });
            return;
        }
        const partnerId = this.props.record.data.partner_id?.[0] || null;
        const partnerName = this.props.record.data.partner_id?.[1] || "";
        this.dialog.add(TwilioSmsMessagingDialog, {
            initialPhone: this.phone,
            initialPartnerId: partnerId,
            initialPartnerName: partnerName,
            onClose: () => {},
        });
    }
}

registry.category("fields").add("twilio_call_button", {
    component: TwilioCallButtonField,
    displayName: _t("Twilio Call Button"),
    supportedTypes: ["char"],
});
