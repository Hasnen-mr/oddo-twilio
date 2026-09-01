/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import * as owl from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { normalizePhoneNumber } from "@twilio_dialer/js/phone_utils";
import { _t } from "@web/core/l10n/translation";
import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { useService } from "@web/core/utils/hooks";

const DRAFT_STORAGE_KEY_PREFIX = "twilio_sms_draft_";
const DRAFT_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000; // 30 days expiry

export class TwilioSmsPopup extends Component {
    static template = "twilio_dialer.TwilioSmsPopup";
    static props = {
        phone: { type: String },
        partnerId: { type: [Number, Boolean], optional: true },
        partnerName: { type: String, optional: true },
        onClose: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
                this.notification = useService("notification");
        this.chatBodyRef = useRef("chatBody");
        this.messageInputRef = useRef("messageInput");

        // Restore saved draft per contact (with 30-day expiration check)
        const savedDraft = this.getDraft();

        this.state = useState({
            loading: true,
            loadingMore: false,
            errorState: false,
            errorMessage: "",
            sending: false,
            messageText: savedDraft || "",
            searchQuery: "",
            messages: [],
            templates: [],
            quickReplies: [],
            hasMore: false,
            currentLimit: 30,
            showPreviewModal: false,
            retryTargetMsg: null, // For Retry Sending confirmation modal
        });

        this._onVisibilityChange = () => {
            if (document.visibilityState === "visible" && !this.state.loading && !this.state.sending) {
                console.log("[Twilio SMS Popup] Window reactivated — performing live refresh.");
                this.loadHistory(this.state.currentLimit, true);
            }
        };

        onWillStart(async () => {
            await Promise.all([
                this.loadHistory(30),
                this.loadTemplates(),
                this.loadQuickReplies(),
            ]);
        });

        onMounted(() => {
            this.scrollToBottom();
            this.focusInput();
            document.addEventListener("visibilitychange", this._onVisibilityChange);
        });

        onWillUnmount(() => {
            document.removeEventListener("visibilitychange", this._onVisibilityChange);
        });
    }

    get normalizedPhone() {
        return normalizePhoneNumber(this.props.phone);
    }

    get draftKey() {
        return `${DRAFT_STORAGE_KEY_PREFIX}${this.normalizedPhone || this.props.phone}`;
    }

    getDraft() {
        try {
            const raw = window.localStorage.getItem(this.draftKey);
            if (!raw) return "";
            const data = JSON.parse(raw);
            if (data && data.timestamp && (Date.now() - data.timestamp < DRAFT_EXPIRY_MS)) {
                return data.text || "";
            } else {
                // Expired draft (> 30 days)
                window.localStorage.removeItem(this.draftKey);
                return "";
            }
        } catch {
            // Fallback for legacy raw string drafts
            try { return window.localStorage.getItem(this.draftKey) || ""; } catch { return ""; }
        }
    }

    saveDraft(val) {
        try {
            if (val) {
                const payload = JSON.stringify({
                    text: val,
                    timestamp: Date.now(),
                });
                window.localStorage.setItem(this.draftKey, payload);
            } else {
                window.localStorage.removeItem(this.draftKey);
            }
        } catch {
            // Ignore quota errors
        }
    }

    clearDraft() {
        try {
            window.localStorage.removeItem(this.draftKey);
        } catch {}
    }

    // Dynamic character counter logic with GSM / Unicode detection & available remaining calculation
    get charInfo() {
        const text = this.state.messageText || "";
        const len = text.length;

        // Check if string contains GSM non-7-bit characters (Unicode / Emojis)
        const isUnicode = /[^\u0000-\u007F]/.test(text);
        const singleLimit = isUnicode ? 70 : 160;
        const multiLimit = isUnicode ? 67 : 153;

        let segments = 0;
        if (len === 0) {
            segments = 0;
        } else if (len <= singleLimit) {
            segments = 1;
        } else {
            segments = Math.ceil(len / multiLimit);
        }

        const totalCapacity = segments > 0 ? (segments === 1 ? singleLimit : segments * multiLimit) : singleLimit;
        const available = Math.max(0, totalCapacity - len);

        return {
            length: len,
            singleLimit: singleLimit,
            segments: segments,
            available: available,
            isUnicode: isUnicode,
        };
    }

    get filteredMessages() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        if (!query) {
            return this.state.messages;
        }
        return this.state.messages.filter((msg) =>
            (msg.body || "").toLowerCase().includes(query) ||
            (msg.from || "").toLowerCase().includes(query) ||
            (msg.to || "").toLowerCase().includes(query) ||
            (msg.status || "").toLowerCase().includes(query)
        );
    }

    focusInput() {
        setTimeout(() => {
            if (this.messageInputRef.el) {
                this.messageInputRef.el.focus();
                // Move cursor to end of text if draft text is restored
                const len = this.messageInputRef.el.value.length;
                this.messageInputRef.el.setSelectionRange(len, len);
            }
        }, 100);
    }

    scrollToBottom() {
        if (this.chatBodyRef.el) {
            this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
        }
    }

    async loadTemplates() {
        try {
            const res = await rpc("/twilio_dialer/sms/get_templates", {
                partner_id: this.props.partnerId || false,
            });
            if (res && res.success) {
                this.state.templates = res.templates || [];
            }
        } catch (e) {
            console.error("[Twilio SMS Popup] Error loading templates:", e);
        }
    }

    async loadQuickReplies() {
        try {
            const res = await rpc("/twilio_dialer/sms/get_quick_replies");
            if (res && res.success) {
                this.state.quickReplies = res.quick_replies || [];
            }
        } catch (e) {
            console.error("[Twilio SMS Popup] Error loading quick replies:", e);
        }
    }

    async loadHistory(limit = 30, silent = false) {
        if (!silent) {
            if (limit > 30) {
                this.state.loadingMore = true;
            } else {
                this.state.loading = true;
            }
        }
        this.state.errorState = false;
        this.state.errorMessage = "";

        try {
            const chatEl = this.chatBodyRef.el;
            const oldScrollHeight = chatEl ? chatEl.scrollHeight : 0;

            const result = await rpc("/twilio_dialer/sms/get_history", {
                phone: this.normalizedPhone || this.props.phone,
                partner_id: this.props.partnerId || false,
                limit: limit,
            });

            if (result && result.success) {
                this.state.messages = result.messages || [];
                this.state.hasMore = !!result.has_more;
                this.state.currentLimit = limit;

                // Maintain scroll position when lazy loading older messages
                if (chatEl && limit > 30) {
                    setTimeout(() => {
                        chatEl.scrollTop = chatEl.scrollHeight - oldScrollHeight;
                    }, 0);
                } else if (!silent) {
                    setTimeout(() => this.scrollToBottom(), 50);
                }
            } else {
                this.state.messages = [];
                this.state.hasMore = false;
                this.state.errorState = true;
                this.state.errorMessage = result?.message || _t("Unable to load conversation. Please check your Twilio configuration or network connection.");
            }
        } catch (err) {
            console.error("[Twilio SMS Popup] Failed to load SMS history:", err);
            this.state.messages = [];
            this.state.errorState = true;
            this.state.errorMessage = _t("Unable to load conversation. Please check your Twilio configuration or network connection.");
        } finally {
            this.state.loading = false;
            this.state.loadingMore = false;
        }
    }

    async onScroll(ev) {
        const el = ev.target;
        if (el.scrollTop < 30 && this.state.hasMore && !this.state.loadingMore && !this.state.loading) {
            const nextLimit = this.state.currentLimit + 30;
            await this.loadHistory(nextLimit);
        }
    }

    onInputMessage(ev) {
        const text = ev.target.value;
        this.state.messageText = text;
        this.saveDraft(text);
    }

    onSelectTemplate(ev) {
        const templateId = parseInt(ev.target.value, 10);
        if (!templateId) return;
        const template = this.state.templates.find((t) => t.id === templateId);
        if (template) {
            // Inserts rendered message with contact variables evaluated
            const textToInsert = template.rendered_body || template.body || "";
            this.state.messageText = textToInsert;
            this.saveDraft(textToInsert);
        }
        ev.target.value = ""; // reset select dropdown
    }

    onInsertQuickReply(text) {
        const current = this.state.messageText ? `${this.state.messageText} ${text}` : text;
        this.state.messageText = current;
        this.saveDraft(current);
    }

    openRetryConfirm(msg) {
        this.state.retryTargetMsg = msg;
    }

    closeRetryConfirm() {
        this.state.retryTargetMsg = null;
    }

    async confirmRetrySending() {
        if (!this.state.retryTargetMsg) return;
        const msg = this.state.retryTargetMsg;
        this.closeRetryConfirm();
        this.state.messageText = msg.body || "";
        this.saveDraft(msg.body || "");
        await this.onSend();
    }

    openPreview() {
        const body = (this.state.messageText || "").trim();
        if (!body) {
            this.notification.add(_t("Please enter a message body before sending."), { type: "warning" });
            return;
        }
        if (body.length > 1600) {
            this.notification.add(_t(`Message length (${body.length} chars) exceeds the maximum Twilio limit of 1600 characters.`), { type: "danger" });
            return;
        }
        this.state.showPreviewModal = true;
    }

    closePreview() {
        this.state.showPreviewModal = false;
    }

    async confirmSendFromPreview() {
        this.closePreview();
        await this.onSend();
    }

    async onSend() {
        const body = (this.state.messageText || "").trim();

        if (!body) {
            this.notification.add(_t("Please enter a message body before sending."), { type: "warning" });
            return;
        }

        if (body.length > 1600) {
            this.notification.add(_t(`Message length (${body.length} chars) exceeds the maximum Twilio limit of 1600 characters.`), { type: "danger" });
            return;
        }

        if (this.state.sending) return;
        this.state.sending = true;

        try {
            const result = await rpc("/twilio_dialer/sms/send", {
                recipient: this.normalizedPhone || this.props.phone,
                body: body,
                partner_id: this.props.partnerId || false,
            });

            if (result && result.success) {
                this.notification.add(_t("SMS sent successfully!"), { type: "success" });
                this.state.messageText = "";
                this.clearDraft(); // Remove saved draft after successful send
                await this.loadHistory(this.state.currentLimit, true);
                this.scrollToBottom();
            } else {
                const msg = result?.message || _t("Failed to send SMS.");
                this.notification.add(msg, { type: "danger" });
            }
        } catch (err) {
            console.error("[Twilio SMS Popup] Send error:", err);
            this.notification.add(_t("Error sending SMS via Twilio. Check network connection."), { type: "danger" });
        } finally {
            this.state.sending = false;
        }
    }

    onCancel() {
        if (typeof this.props.close === "function") {
            this.props.close();
        } else if (typeof this.props.onClose === "function") {
            this.props.onClose();
        }
    }
}