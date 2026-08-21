/** @odoo-module **/

import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { TwilioSmsPopup } from "@twilio_dialer/js/sms_popup";
import { TwilioSmsMessagingDialog } from "@twilio_dialer/js/sms_messaging_dialog";

const DRAFT_STORAGE_KEY_PREFIX = "twilio_sms_draft_";
const DRAFT_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export class TwilioSmsWorkspaceClientAction extends Component {
    static template = "twilio_dialer.TwilioSmsWorkspaceClientAction";

    setup() {
                this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            loading: true,
            counts: {
                contacts: 0,
                logs: 0,
                templates: 0,
                quick_replies: 0,
            },
            drafts: [],
            recentLogs: [],
        });

        onWillStart(async () => {
            await this.loadWorkspaceData();
        });
    }

    async loadWorkspaceData() {
        this.state.loading = true;
        try {
            // Load record counts
            const res = await rpc("/twilio_dialer/sms/workspace_counts");
            if (res && res.success) {
                this.state.counts = res.counts;
            }

            // Scan localStorage for active unsent SMS drafts
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

                        // Filter unexpired drafts (< 30 days)
                        if (text.trim() && (Date.now() - timestamp < DRAFT_EXPIRY_MS)) {
                            const dateStr = new Date(timestamp).toLocaleDateString([], {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                            });
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

            // Load recent SMS logs for the embedded workspace table
            const logsRes = await rpc("/twilio_dialer/sms/get_recent_logs", { limit: 50 });
            if (logsRes && logsRes.success) {
                this.state.recentLogs = logsRes.logs || [];
            }
        } catch (err) {
            console.error("[SMS Workspace] Failed to load workspace data:", err);
        } finally {
            this.state.loading = false;
        }
    }

    openMessagesList() {
        // Opens WhatsApp-style full-screen 2-panel messaging dialog
        this.dialog.add(TwilioSmsMessagingDialog, {
            onClose: () => this.loadWorkspaceData(),
        });
    }

    scrollToLogs() {
        const elem = document.getElementById("o_twilio_sms_logs_section");
        if (elem) {
            elem.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    openSmsLogs() {
        this.scrollToLogs();
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

    openSmsForPhone(phone, partnerId, partnerName) {
        if (!phone) return;
        this.dialog.add(TwilioSmsMessagingDialog, {
            initialPhone: phone,
            initialPartnerId: partnerId || false,
            initialPartnerName: partnerName || "Contact",
            onClose: () => this.loadWorkspaceData(),
        });
    }

    openDraft(draft) {
        this.dialog.add(TwilioSmsPopup, {
            phone: draft.phone,
            partnerId: false,
            partnerName: `Draft (${draft.phone})`,
            onClose: () => this.loadWorkspaceData(),
        });
    }

    clearDraft(draft, ev) {
        ev.stopPropagation();
        try {
            const key = `${DRAFT_STORAGE_KEY_PREFIX}${draft.phone}`;
            localStorage.removeItem(key);
            this.loadWorkspaceData();
        } catch (e) {
            console.error("[SMS Workspace] Error clearing draft:", e);
        }
    }
}

registry.category("actions").add("twilio_sms_workspace_action", TwilioSmsWorkspaceClientAction);