/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { TwilioSmsPopup } from "@twilio_dialer_pro/js/sms_popup";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const AVATAR_COLORS = [
    "#0284c7", "#7c3aed", "#059669", "#d97706",
    "#dc2626", "#0891b2", "#4f46e5", "#db2777",
];

export class TwilioSmsMessagingDialog extends Component {
    static template = "twilio_dialer_pro.TwilioSmsMessagingDialog";
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
            conversations: [],
            selectedContact: null,
        });

        onWillStart(async () => {
            await this.loadConversations();
            if (this.props.initialPhone) {
                this.selectContactByPhone(this.props.initialPhone, this.props.initialPartnerId, this.props.initialPartnerName);
            }
        });
    }

    async loadConversations() {
        this.state.loading = true;
        try {
            const res = await rpc("/twilio_dialer/sms/get_conversations");
            if (res && res.success) {
                this.state.conversations = res.conversations || [];
                if (this.state.conversations.length > 0 && !this.state.selectedContact) {
                    if (this.props.initialPhone) {
                        const matched = this.state.conversations.find((c) => c.phone === this.props.initialPhone);
                        this.state.selectedContact = matched || {
                            phone: this.props.initialPhone,
                            partner_id: this.props.initialPartnerId || false,
                            name: this.props.initialPartnerName || this.props.initialPhone,
                        };
                    } else {
                        this.state.selectedContact = this.state.conversations[0];
                    }
                }
            }
        } catch (e) {
            console.error("[Twilio Messaging Dialog] Error loading conversations:", e);
        } finally {
            this.state.loading = false;
        }
    }

    selectContactByPhone(phone, partnerId, partnerName) {
        this.state.selectedContact = {
            partner_id: partnerId || false,
            name: partnerName || phone,
            phone: phone,
        };
    }

    get filteredConversations() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (!query) {
            return this.state.conversations;
        }
        return this.state.conversations.filter((c) =>
            (c.name || "").toLowerCase().includes(query) ||
            (c.phone || "").toLowerCase().includes(query) ||
            (c.company || "").toLowerCase().includes(query) ||
            (c.last_message || "").toLowerCase().includes(query)
        );
    }

    getAvatarColor(name) {
        if (!name) return AVATAR_COLORS[0];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
    }

    getInitials(name) {
        if (!name) return "?";
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return name.substring(0, 2).toUpperCase();
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
