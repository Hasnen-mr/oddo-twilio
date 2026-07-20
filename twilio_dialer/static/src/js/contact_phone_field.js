/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { PhoneField, phoneField, formPhoneField } from "@web/views/fields/phone/phone_field";

class ContactCallButton extends Component {
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
            this.notification.add(_t("This contact does not have a phone number."), {
                type: "warning",
            });
            return;
        }
        this.dialer.open({
            phone: this.phone,
            partnerId: this.props.record.resId,
            partnerName: this.props.record.data.name || "",
        });
    }
}

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

patch(phoneField, patchDescription());
patch(formPhoneField, patchDescription());
