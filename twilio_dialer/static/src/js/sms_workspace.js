/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { TwilioSmsPopup } from "@twilio_dialer/js/sms_popup";
import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DRAFT_STORAGE_KEY_PREFIX = "twilio_sms_draft_";
const DRAFT_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000;

const AVATAR_COLORS = [
    "#0284c7", "#7c3aed", "#059669", "#d97706",
    "#dc2626", "#0891b2", "#4f46e5", "#db2777",
    "#2563eb", "#0d9488", "#ca8a04", "#9333ea",
];

export class TwilioSmsWorkspaceClientAction extends Component {
    static template = "twilio_dialer.TwilioSmsWorkspaceClientAction";
    static components = { TwilioSmsPopup };

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.dialer = useService("twilio_dialer", { optional: true });

        this.state = useState({
            loading: true,
            filterTab: "all",
            searchQuery: "",
            conversations: [],
            selectedContact: null,
            counts: {
                contacts: 0,
                logs: 0,
                templates: 0,
                quick_replies: 0,
                sent: 0,
                received: 0,
            },
            drafts: [],
            recentLogs: [],
            newNumberInput: "",
            showNewChatInput: false,
        });

        onWillStart(async () => {
            await this.loadWorkspaceData();
        });
    }

    async loadWorkspaceData() {
        this.state.loading = true;
        try {
            const [countsRes, convsRes, logsRes] = await Promise.all([
                rpc("/twilio_dialer/sms/workspace_counts").catch(() => ({})),
                rpc("/twilio_dialer/sms/get_conversations").catch(() => ({})),
                rpc("/twilio_dialer/sms/get_recent_logs", { limit: 100 }).catch(() => ({})),
            ]);

            if (countsRes && countsRes.success && countsRes.counts) {
                this.state.counts = countsRes.counts;
            }

            if (convsRes && convsRes.success) {
                this.state.conversations = convsRes.conversations || [];
            }

            if (logsRes && logsRes.success) {
                this.state.recentLogs = logsRes.logs || [];
            }

            this.loadDrafts();

            if (!this.state.selectedContact && this.state.conversations.length > 0) {
                this.state.selectedContact = this.state.conversations[0];
            }
        } catch (err) {
            console.error("[SMS Workspace] Error loading data:", err);
        } finally {
            this.state.loading = false;
        }
    }

    loadDrafts() {
        const foundDrafts = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(DRAFT_STORAGE_KEY_PREFIX)) {
                const phone = key.replace(DRAFT_STORAGE_KEY_PREFIX, "");
                try {
                    const raw = localStorage.getItem(key);
                    let text = "";
                    let timestamp = Date.now();
                    try {
                        const data = JSON.parse(raw);
                        text = data.text || "";
                        timestamp = data.timestamp || Date.now();
                    } catch {
                        text = raw || "";
                    }

                    if (text.trim() && (Date.now() - timestamp < DRAFT_EXPIRY_MS)) {
                        const dateStr = this.formatDate(timestamp);
                        foundDrafts.push({
                            phone: phone,
                            text: text,
                            preview: text.length > 55 ? text.substring(0, 55) + "..." : text,
                            timestampStr: dateStr,
                        });
                    }
                } catch (e) {
                    console.error("[SMS Workspace] Error reading draft key:", key, e);
                }
            }
        }
        this.state.drafts = foundDrafts;
    }

    get filteredConversations() {
        let list = this.state.conversations;

        if (this.state.filterTab === "unread") {
            list = list.filter((c) => c.unread > 0 || c.last_direction === "incoming" || c.last_direction === "inbound");
        } else if (this.state.filterTab === "drafts") {
            const draftPhones = new Set(this.state.drafts.map((d) => d.phone));
            list = list.filter((c) => draftPhones.has(c.phone));
        }

        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (query) {
            list = list.filter((c) =>
                (c.name || "").toLowerCase().includes(query) ||
                (c.phone || "").toLowerCase().includes(query) ||
                (c.company || "").toLowerCase().includes(query) ||
                (c.last_message || "").toLowerCase().includes(query)
            );
        }

        return list;
    }

    getAvatarColor(name) {
        if (!name) return AVATAR_COLORS[0];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        const index = Math.abs(hash) % AVATAR_COLORS.length;
        return AVATAR_COLORS[index];
    }

    getInitials(name) {
        if (!name) return "?";
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }

    formatDate(dateVal) {
        if (!dateVal) return "";
        try {
            const d = new Date(dateVal);
            if (isNaN(d.getTime())) return String(dateVal);
            const now = new Date();
            const isToday = d.toDateString() === now.toDateString();
            if (isToday) {
                return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            }
            const yesterday = new Date(now);
            yesterday.setDate(now.getDate() - 1);
            if (d.toDateString() === yesterday.toDateString()) {
                return "Yesterday";
            }
            if (d.getFullYear() === now.getFullYear()) {
                return d.toLocaleDateString([], { month: "short", day: "numeric" });
            }
            return d.toLocaleDateString([], { month: "numeric", day: "numeric", year: "2-digit" });
        } catch {
            return String(dateVal);
        }
    }

    selectConversation(conv) {
        this.state.selectedContact = conv;
        if (this.state.filterTab === "logs") {
            this.state.filterTab = "all";
        }
    }

    setFilterTab(tab) {
        this.state.filterTab = tab;
    }

    toggleNewChat() {
        this.state.showNewChatInput = !this.state.showNewChatInput;
        this.state.newNumberInput = "";
    }

    startNewChatWithNumber() {
        const num = (this.state.newNumberInput || "").trim();
        if (!num) return;
        this.state.selectedContact = {
            phone: num,
            name: num,
            partner_id: false,
            last_message: "",
            last_date: "",
            unread: 0,
        };
        this.state.showNewChatInput = false;
        this.state.newNumberInput = "";
    }

    openSmsTemplates() {
        this.action.doAction("twilio_dialer.action_twilio_sms_template", {
            clearBreadcrumbs: false,
        });
    }

    openQuickReplies() {
        this.action.doAction("twilio_dialer.action_twilio_sms_quick_reply", {
            clearBreadcrumbs: false,
        });
    }

    openPartnerForm(partnerId, ev) {
        if (ev) ev.stopPropagation();
        if (!partnerId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: partnerId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    makeCall(phone, partnerId, partnerName, ev) {
        if (ev) ev.stopPropagation();
        if (!phone) return;
        if (this.dialer) {
            if (typeof this.dialer.open === "function") {
                this.dialer.open({
                    phone: phone,
                    partnerId: partnerId || null,
                    partnerName: partnerName || phone,
                });
            } else if (typeof this.dialer.openDialer === "function") {
                this.dialer.openDialer({
                    phone: phone,
                    partnerId: partnerId || null,
                    partnerName: partnerName || phone,
                });
            }
        }
    }

    openDraft(draft) {
        this.state.selectedContact = {
            phone: draft.phone,
            name: `Draft (${draft.phone})`,
            partner_id: false,
            last_message: draft.text,
            last_date: draft.timestampStr,
            unread: 0,
        };
    }

    clearDraft(draft, ev) {
        if (ev) ev.stopPropagation();
        try {
            const key = `${DRAFT_STORAGE_KEY_PREFIX}${draft.phone}`;
            localStorage.removeItem(key);
            this.loadDrafts();
        } catch (e) {
            console.error("[SMS Workspace] Error clearing draft:", e);
        }
    }

    onChatClosed() {
        this.loadWorkspaceData();
    }
}

registry.category("actions").add("twilio_sms_workspace_action", TwilioSmsWorkspaceClientAction, { force: true });
