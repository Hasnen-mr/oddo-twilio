/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { PhoneField, phoneField, formPhoneField } from "@web/views/fields/phone/phone_field";
import { TwilioSmsPopup } from "./sms_popup";
import { TwilioSmsMessagingDialog } from "./sms_messaging_dialog";

export class ContactSmsButton extends Component {
    static template = "twilio_dialer.ContactSmsButton";
    static props = {
        record: { type: Object },
        name: { type: String },
    };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }

    get phone() {
        return this.props.record.data[this.props.name] || "";
    }

    openSms() {
        if (!this.phone) {
            this.notification.add(_t("No phone number available to send SMS."), {
                type: "warning",
            });
            return;
        }

        const partnerId = this.props.record.data.partner_id?.[0] || this.props.record.resId || null;
        const partnerName = this.props.record.data.partner_id?.[1]
            || this.props.record.data.name
            || "";

        this.dialog.add(TwilioSmsMessagingDialog, {
            initialPhone: this.phone,
            initialPartnerId: partnerId,
            initialPartnerName: partnerName,
            onClose: () => {},
        });
    }
}

// Inject ContactSmsButton into PhoneField alongside ContactCallButton
patch(PhoneField, {
    components: {
        ...PhoneField.components,
        ContactSmsButton,
    },
});
