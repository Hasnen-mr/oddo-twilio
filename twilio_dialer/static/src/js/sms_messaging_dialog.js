/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { TwilioSmsPopup } from "@twilio_dialer/js/sms_popup";
import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

export class TwilioSmsMessagingDialog extends Component {
    static template = "twilio_dialer.TwilioSmsMessagingDialog";
    static components = { TwilioSmsPopup };
    static props = {
        close: { type: Function, optional: true },
        onClose: { type: Function, optional: true },
        initialPartnerId: { type: [Number, Boolean], optional: true },
        initialPhone: { type: String, optional: true },
        initialPartnerName: { type: String, optional: true },
    };

    setup() {
                this.state = useState({
            loading: true,
            searchQuery: "",
            contacts: [],
            selectedContact: null,
        });

        onWillStart(async () => {
            await this.loadContacts();
            if (this.props.initialPhone) {
                this.selectContactByPhone(this.props.initialPhone, this.props.initialPartnerId, this.props.initialPartnerName);
            }
        });
    }

    async loadContacts() {
        this.state.loading = true;
        try {
            const res = await rpc("/twilio_dialer/sms/get_contacts");
            if (res && res.success) {
                this.state.contacts = res.contacts || [];
                // If initial selection exists, select it; else pick first contact if available
                if (this.state.contacts.length > 0 && !this.state.selectedContact) {
                    if (this.props.initialPhone) {
                        const matched = this.state.contacts.find((c) => c.phone === this.props.initialPhone);
                        if (matched) {
                            this.state.selectedContact = matched;
                        } else {
                            this.state.selectedContact = this.state.contacts[0];
                        }
                    } else {
                        this.state.selectedContact = this.state.contacts[0];
                    }
                }
            }
        } catch (e) {
            console.error("[Twilio Messaging Dialog] Error loading contacts:", e);
        } finally {
            this.state.loading = false;
        }
    }

    selectContactByPhone(phone, partnerId, partnerName) {
        this.state.selectedContact = {
            id: partnerId || false,
            name: partnerName || "Contact",
            phone: phone,
        };
    }

    get filteredContacts() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (!query) {
            return this.state.contacts;
        }
        return this.state.contacts.filter((c) =>
            (c.name || "").toLowerCase().includes(query) ||
            (c.phone || "").toLowerCase().includes(query) ||
            (c.company || "").toLowerCase().includes(query)
        );
    }

    onSelectContact(contact) {
        this.state.selectedContact = contact;
    }

    onClose() {
        if (typeof this.props.close === "function") {
            this.props.close();
        } else if (typeof this.props.onClose === "function") {
            this.props.onClose();
        }
    }
}