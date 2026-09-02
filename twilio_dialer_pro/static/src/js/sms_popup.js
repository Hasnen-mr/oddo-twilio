/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { normalizePhoneNumber } from "@twilio_dialer_pro/js/phone_utils";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const DRAFT_STORAGE_KEY_PREFIX = "twilio_sms_draft_";
const DRAFT_EXPIRY_MS = 30 * 24 * 60 * 60 * 1000;

// Global In-Memory Per-Contact Context Store
// Maps normalizedPhone -> { messageText, messages, searchQuery, scrollPos, currentLimit, hasMore, lastLoadedAt }
const contactContextMap = new Map();

let globalTemplatesCache = null;
let globalQuickRepliesCache = null;

export class TwilioSmsPopup extends Component {
    static template = "twilio_dialer_pro.TwilioSmsPopup";
    static props = {
        phone: { type: String },
        partnerId: { type: [Number, Boolean], optional: true },
        partnerName: { type: String, optional: true },
        isEmbedded: { type: Boolean, optional: true },
        onClose: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.dialer = useService("twilio_dialer", { optional: true });
        this.chatBodyRef = useRef("chatBody");
        this.messageInputRef = useRef("messageInput");

        const initialKey = this.getPhoneKey(this.props.phone);
        const existingCtx = contactContextMap.get(initialKey);
        const initialDraft = existingCtx?.messageText || this.getDraftFromStorage(this.props.phone);

        this.state = useState({
            loading: true,
            loadingMore: false,
            errorState: false,
            errorMessage: "",
            sending: false,
            messageText: initialDraft || "",
            searchQuery: existingCtx?.searchQuery || "",
            messages: existingCtx?.messages || [],
            templates: globalTemplatesCache || [],
            quickReplies: globalQuickRepliesCache || [],
            hasMore: existingCtx?.hasMore || false,
            currentLimit: existingCtx?.currentLimit || 30,
            showPreviewModal: false,
            retryTargetMsg: null,
        });

        this._onVisibilityChange = () => {
            if (document.visibilityState === "visible" && !this.state.loading && !this.state.sending) {
                this.loadHistory(this.state.currentLimit, true);
            }
        };

        onWillStart(async () => {
            this.state.loading = true;
            const startTime = Date.now();
            await Promise.all([
                this.loadHistory(this.state.currentLimit, false),
                this.loadTemplates(),
                this.loadQuickReplies(),
            ]);
            const elapsed = Date.now() - startTime;
            if (elapsed < 150) {
                await new Promise((resolve) => setTimeout(resolve, 150 - elapsed));
            }
            this.state.loading = false;
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.phone && nextProps.phone !== this.props.phone) {
                // 1. Save outgoing contact's context
                this.saveCurrentContactContext();

                // 2. Load incoming contact's context
                const nextKey = this.getPhoneKey(nextProps.phone);
                const nextCtx = contactContextMap.get(nextKey);
                const nextDraft = nextCtx?.messageText || this.getDraftFromStorage(nextProps.phone);

                this.state.messageText = nextDraft || "";
                this.state.searchQuery = nextCtx?.searchQuery || "";
                this.state.errorState = false;
                this.state.loading = true; // Short skeleton feedback
                this.state.currentLimit = nextCtx?.currentLimit || 30;

                const startTime = Date.now();
                await this.loadHistoryForPhone(nextProps.phone, nextProps.partnerId, this.state.currentLimit, false);
                const elapsed = Date.now() - startTime;
                if (elapsed < 150) {
                    await new Promise((resolve) => setTimeout(resolve, 150 - elapsed));
                }
                this.state.loading = false;

                // 3. Restore scroll position or scroll to bottom
                if (nextCtx && typeof nextCtx.scrollPos === "number") {
                    setTimeout(() => {
                        if (this.chatBodyRef.el) {
                            this.chatBodyRef.el.scrollTop = nextCtx.scrollPos;
                        }
                    }, 20);
                } else {
                    this.scrollToBottom();
                }
                this.focusInput();
            }
        });

        onMounted(() => {
            this.scrollToBottom();
            this.focusInput();
            document.addEventListener("visibilitychange", this._onVisibilityChange);
        });

        onWillUnmount(() => {
            document.removeEventListener("visibilitychange", this._onVisibilityChange);
            this.saveCurrentContactContext();
        });
    }

    getPhoneKey(phone) {
        return normalizePhoneNumber(phone) || phone || "";
    }

    get normalizedPhone() {
        return normalizePhoneNumber(this.props.phone);
    }

    saveCurrentContactContext() {
        const key = this.getPhoneKey(this.props.phone);
        if (!key) return;

        const scrollPos = this.chatBodyRef.el ? this.chatBodyRef.el.scrollTop : 0;
        contactContextMap.set(key, {
            messageText: this.state.messageText,
            messages: this.state.messages,
            searchQuery: this.state.searchQuery,
            scrollPos: scrollPos,
            currentLimit: this.state.currentLimit,
            hasMore: this.state.hasMore,
            lastLoadedAt: Date.now(),
        });

        // Persist draft to storage
        this.saveDraftToStorage(this.props.phone, this.state.messageText);
    }

    getDraftFromStorage(phone) {
        try {
            const key = `${DRAFT_STORAGE_KEY_PREFIX}${this.getPhoneKey(phone)}`;
            const raw = window.localStorage.getItem(key);
            if (!raw) return "";
            const data = JSON.parse(raw);
            if (data && data.timestamp && (Date.now() - data.timestamp < DRAFT_EXPIRY_MS)) {
                return data.text || "";
            } else {
                window.localStorage.removeItem(key);
                return "";
            }
        } catch {
            return "";
        }
    }

    saveDraftToStorage(phone, val) {
        try {
            const key = `${DRAFT_STORAGE_KEY_PREFIX}${this.getPhoneKey(phone)}`;
            if (val && val.trim()) {
                const payload = JSON.stringify({
                    text: val,
                    timestamp: Date.now(),
                });
                window.localStorage.setItem(key, payload);
            } else {
                window.localStorage.removeItem(key);
            }
        } catch {}
    }

    clearDraftForPhone(phone) {
        try {
            const key = `${DRAFT_STORAGE_KEY_PREFIX}${this.getPhoneKey(phone)}`;
            window.localStorage.removeItem(key);
            const ctxKey = this.getPhoneKey(phone);
            if (contactContextMap.has(ctxKey)) {
                contactContextMap.get(ctxKey).messageText = "";
            }
        } catch {}
    }

    get charInfo() {
        const text = this.state.messageText || "";
        const len = text.length;
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
                const len = this.messageInputRef.el.value.length;
                this.messageInputRef.el.setSelectionRange(len, len);
            }
        }, 50);
    }

    scrollToBottom() {
        setTimeout(() => {
            if (this.chatBodyRef.el) {
                this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
            }
        }, 30);
    }

    async loadTemplates() {
        if (globalTemplatesCache) {
            this.state.templates = globalTemplatesCache;
            return;
        }
        try {
            const res = await rpc("/twilio_dialer/sms/get_templates", {
                partner_id: this.props.partnerId || false,
            });
            if (res && res.success) {
                globalTemplatesCache = res.templates || [];
                this.state.templates = globalTemplatesCache;
            }
        } catch (e) {
            console.error("[Twilio SMS] Error loading templates:", e);
        }
    }

    async loadQuickReplies() {
        if (globalQuickRepliesCache) {
            this.state.quickReplies = globalQuickRepliesCache;
            return;
        }
        try {
            const res = await rpc("/twilio_dialer/sms/get_quick_replies");
            if (res && res.success) {
                globalQuickRepliesCache = res.quick_replies || [];
                this.state.quickReplies = globalQuickRepliesCache;
            }
        } catch (e) {
            console.error("[Twilio SMS] Error loading quick replies:", e);
        }
    }

    async loadHistory(limit = 30, silent = false) {
        return this.loadHistoryForPhone(this.props.phone, this.props.partnerId, limit, silent);
    }

    async loadHistoryForPhone(phone, partnerId, limit = 30, silent = false) {
        if (!silent && limit > 30) {
            this.state.loadingMore = true;
        }
        this.state.errorState = false;
        this.state.errorMessage = "";

        try {
            const norm = normalizePhoneNumber(phone) || phone;
            const result = await rpc("/twilio_dialer/sms/get_history", {
                phone: norm,
                partner_id: partnerId || false,
                limit: limit,
            });

            if (result && result.success) {
                this.state.messages = result.messages || [];
                this.state.hasMore = !!result.has_more;
                this.state.currentLimit = limit;

                // Update context cache
                const key = this.getPhoneKey(phone);
                const ctx = contactContextMap.get(key) || {};
                ctx.messages = this.state.messages;
                ctx.hasMore = this.state.hasMore;
                ctx.currentLimit = limit;
                contactContextMap.set(key, ctx);

                if (!silent && limit === 30) {
                    this.scrollToBottom();
                }
            } else {
                this.state.errorState = true;
                this.state.errorMessage = result?.message || _t("Unable to load conversation.");
            }
        } catch (err) {
            console.error("[Twilio SMS] Failed to load SMS history:", err);
            this.state.errorState = true;
            this.state.errorMessage = _t("Unable to load conversation. Please check connection.");
        } finally {
            this.state.loadingMore = false;
        }
    }

    async onScroll(ev) {
        const el = ev.target;
        // Save scroll position into context
        const key = this.getPhoneKey(this.props.phone);
        if (contactContextMap.has(key)) {
            contactContextMap.get(key).scrollPos = el.scrollTop;
        }

        if (el.scrollTop < 30 && this.state.hasMore && !this.state.loadingMore && !this.state.loading) {
            const nextLimit = this.state.currentLimit + 30;
            await this.loadHistory(nextLimit);
        }
    }

    onInputMessage(ev) {
        const text = ev.target.value;
        this.state.messageText = text;
        this.saveDraftToStorage(this.props.phone, text);
        const key = this.getPhoneKey(this.props.phone);
        if (contactContextMap.has(key)) {
            contactContextMap.get(key).messageText = text;
        }
    }

    onKeyDownTextarea(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSend();
        }
    }

    onSelectTemplate(ev) {
        const templateId = parseInt(ev.target.value, 10);
        if (!templateId) return;
        const template = this.state.templates.find((t) => t.id === templateId);
        if (template) {
            const textToInsert = template.rendered_body || template.body || "";
            this.state.messageText = textToInsert;
            this.saveDraftToStorage(this.props.phone, textToInsert);
            const key = this.getPhoneKey(this.props.phone);
            if (contactContextMap.has(key)) {
                contactContextMap.get(key).messageText = textToInsert;
            }
        }
        ev.target.value = "";
    }

    onInsertQuickReply(text) {
        const current = this.state.messageText ? `${this.state.messageText} ${text}` : text;
        this.state.messageText = current;
        this.saveDraftToStorage(this.props.phone, current);
        const key = this.getPhoneKey(this.props.phone);
        if (contactContextMap.has(key)) {
            contactContextMap.get(key).messageText = current;
        }
    }

    makeCall(ev) {
        if (ev) ev.stopPropagation();
        if (!this.props.phone) return;
        if (this.dialer) {
            if (typeof this.dialer.open === "function") {
                this.dialer.open({
                    phone: this.props.phone,
                    partnerId: this.props.partnerId || null,
                    partnerName: this.props.partnerName || this.props.phone,
                });
            } else if (typeof this.dialer.openDialer === "function") {
                this.dialer.openDialer({
                    phone: this.props.phone,
                    partnerId: this.props.partnerId || null,
                    partnerName: this.props.partnerName || this.props.phone,
                });
            }
        }
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
        this.saveDraftToStorage(this.props.phone, msg.body || "");
        await this.onSend();
    }

    openPreview() {
        const body = (this.state.messageText || "").trim();
        if (!body) {
            this.notification.add(_t("Please enter a message body before sending."), { type: "warning" });
            return;
        }
        if (body.length > 1600) {
            this.notification.add(_t(`Message length (${body.length} chars) exceeds maximum limit of 1600 characters.`), { type: "danger" });
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
        if (!body) return;

        if (body.length > 1600) {
            this.notification.add(_t(`Message length exceeds 1600 characters.`), { type: "danger" });
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
                this.clearDraftForPhone(this.props.phone);
                await this.loadHistory(this.state.currentLimit, true);
                this.scrollToBottom();
            } else {
                const msg = result?.message || _t("Failed to send SMS.");
                this.notification.add(msg, { type: "danger" });
            }
        } catch (err) {
            console.error("[Twilio SMS] Send error:", err);
            this.notification.add(_t("Error sending SMS via Twilio."), { type: "danger" });
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
