/** @odoo-module **/

import { AIChatSkeleton } from "@mcp_claude/js/components/ai_chat_skeleton";
import { Component, markup, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { routerBus } from "@web/core/browser/router";
import { useBus, useService } from "@web/core/utils/hooks";

export class AIChatWindow extends Component {
    static template = "mcp_claude.AIChatWindow";
    static components = { AIChatSkeleton };
    static props = {
        onClose: Function,
    };

    setup() {
        this.aiService = useService("ai_chat_service");
        this.notification = useService("notification");
        this.chatBodyRef = useRef("chatBody");
        
        this.isUserScrolledUp = false;
        this.navDebounceTimer = null;
        this.fastLoadTimer = null;
        this.isSwitchingContext = false;
        this.activeAbortController = null;

        // Map to preserve unsent prompt draft text per conversation/scope
        this.draftPrompts = {};

        this.state = useState({
            initialLoading: true,        // Full skeleton on first component mount
            isSwitchingThread: false,     // Semi-transparent overlay on context switch
            sending: false,
            promptText: "",
            history: [],
            activeModel: null,
            activeResId: null,
            activeScope: "global",
            activeConvId: null,
            title: "Claude AI Copilot",
            capabilities: null,
            isExpanded: false,           // Compact default (false) vs Expanded (true)
        });

        // Single-tick debounced event listeners for Odoo Action Manager and URL Router
        if (this.env && this.env.bus) {
            useBus(this.env.bus, "ACTION_MANAGER:UPDATE", (ev) => this.handleEvent("ACTION_MANAGER:UPDATE", ev));
            useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", (ev) => this.handleEvent("ACTION_MANAGER:UI-UPDATED", ev));
        }
        if (typeof routerBus !== "undefined" && routerBus && typeof routerBus.addEventListener === "function") {
            useBus(routerBus, "ROUTE_CHANGE", (ev) => this.handleEvent("ROUTE_CHANGE", ev));
        }

        onWillStart(async () => {
            await this.loadChat(null, true);
        });

        onMounted(() => {
            this.scrollToBottom(true);
        });
    }

    handleEvent(eventName, ev) {
        const context = this.aiService.collectActiveContext();
        const newModel = context.resModel || null;
        const newResId = context.resId || null;

        if (this.navDebounceTimer) {
            clearTimeout(this.navDebounceTimer);
        }
        this.navDebounceTimer = setTimeout(() => {
            this.onNavigationChange(eventName, newModel, newResId);
        }, 120);
    }

    async onNavigationChange(triggerEvent, newModel, newResId) {
        // Enforce Global Scope Baseline: Do not switch AI conversation threads on view navigation
        return;
    }

    toggleExpand() {
        this.state.isExpanded = !this.state.isExpanded;
    }

    async onNewChat() {
        this.state.history = [];
        this.state.promptText = "";
        await this.loadChat(null, true);
        this.notification.add("New Global Conversation started.", { type: "info", title: "Claude AI" });
    }

    async loadChat(forcedScope = null, isInitial = false) {
        if (this.activeAbortController) {
            this.activeAbortController.abort();
            this.activeAbortController = null;
        }

        const abortController = new AbortController();
        this.activeAbortController = abortController;

        if (this.state.activeConvId && this.state.promptText) {
            this.draftPrompts[this.state.activeConvId] = this.state.promptText;
        }

        if (isInitial) {
            this.state.initialLoading = true;
        } else {
            if (this.fastLoadTimer) clearTimeout(this.fastLoadTimer);
            this.fastLoadTimer = setTimeout(() => {
                if (this.activeAbortController === abortController) {
                    this.state.isSwitchingThread = true;
                }
            }, 100);
        }

        try {
            const scope = "global";

            const res = await this.aiService.initChat(
                "global",
                null,
                null,
                null,
                abortController.signal
            );

            if (res && res.aborted) {
                return;
            }

            if (res && res.success) {
                this.state.activeScope = "global";
                this.state.activeConvId = res.conversation_id;
                this.state.history = res.history || [];
                this.state.title = res.title || "Claude AI Copilot";
                this.state.capabilities = res.capabilities || null;

                this.state.promptText = this.draftPrompts[res.conversation_id] || "";
            } else if (!res) {
                this.notification.add("Failed to initialize AI Chat session. Please try again.", { type: "warning" });
            }
        } catch (err) {
            console.error("[AIChatWindow loadChat Error]", err);
        } finally {
            if (this.fastLoadTimer) clearTimeout(this.fastLoadTimer);
            this.state.initialLoading = false;
            this.state.isSwitchingThread = false;
            if (this.activeAbortController === abortController) {
                this.activeAbortController = null;
            }
            this.scrollToBottom(true);
        }
    }

    async setScope(scope) {
        return;
    }

    onScroll(ev) {
        const el = ev.target;
        const threshold = 60;
        const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
        this.isUserScrolledUp = !isAtBottom;
    }

    scrollToBottom(force = false) {
        setTimeout(() => {
            if (!this.chatBodyRef.el) return;
            if (force || !this.isUserScrolledUp) {
                this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
            }
        }, 50);
    }

    async onSendMessage() {
        const text = (this.state.promptText || "").trim();
        if (!text || this.state.sending) return;

        this.state.sending = true;
        this.state.promptText = "";
        if (this.state.activeConvId) {
            delete this.draftPrompts[this.state.activeConvId];
        }

        this.isUserScrolledUp = false;
        
        this.state.history.push({
            id: Date.now(),
            role: "user",
            content: text,
            block_type: "markdown"
        });

        this.scrollToBottom(true);

        const res = await this.aiService.sendMessage(text);
        if (res && res.success) {
            if (res.response_block) {
                this.state.history.push({
                    id: Date.now() + 1,
                    role: "assistant",
                    content: res.response_block.content,
                    block_type: res.response_block.block_type || "markdown"
                });
            }
        } else {
            this.state.history.push({
                id: Date.now() + 1,
                role: "assistant",
                content: `Error: ${res.error || "Failed to generate response"}`,
                block_type: "error"
            });
        }
        this.state.sending = false;
        this.scrollToBottom();
    }

    renderFormattedContent(content) {
        if (!content) return markup("");
        let text = String(content);

        const codeBlocks = [];
        text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const placeholder = `___CODEBLOCK_${codeBlocks.length}___`;
            const langLabel = lang ? `<div class="claude-code-header text-muted border-bottom px-3 py-1 bg-light d-flex justify-content-between align-items-center" style="font-size:11px;"><span class="fw-bold text-uppercase">${lang}</span></div>` : '';
            const escapedCode = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            codeBlocks.push(`${langLabel}<pre class="m-0 p-3"><code>${escapedCode.trim()}</code></pre>`);
            return placeholder;
        });

        const hasHtmlTags = /<[a-z/][\s\S]*>/i.test(text);

        let formatted = text;
        if (!hasHtmlTags) {
            formatted = formatted
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");

            formatted = formatted.replace(/(?:^|\n)((?:\|[^\n]+\|\r?\n)+)/g, (match, tableStr) => {
                const lines = tableStr.trim().split('\n').map(l => l.trim()).filter(l => l);
                if (lines.length < 2) return match;
                
                let html = '<div class="table-responsive my-2"><table class="table table-sm table-bordered table-hover border rounded-3 overflow-hidden mb-0 align-middle"><thead class="table-light">';
                let isHeader = true;

                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(line)) {
                        isHeader = false;
                        continue;
                    }
                    const cells = line.split('|').slice(1, -1).map(c => c.trim());
                    if (isHeader) {
                        html += '<tr>' + cells.map(c => `<th class="fw-semibold px-3 py-2 bg-light text-dark">${c}</th>`).join('') + '</tr></thead><tbody>';
                        isHeader = false;
                    } else {
                        html += '<tr>' + cells.map(c => `<td class="px-3 py-2">${c}</td>`).join('') + '</tr>';
                    }
                }
                html += '</tbody></table></div>';
                return html;
            });

            formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
            formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            formatted = formatted.replace(/(?:^|\n)[*|-]\s+(.*)/g, '<li class="ms-3">$1</li>');
            formatted = formatted.replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>');
        }

        codeBlocks.forEach((block, idx) => {
            formatted = formatted.replace(`___CODEBLOCK_${idx}___`, `<div class="claude-code-container my-2 border rounded-3 overflow-hidden bg-dark text-light">${block}</div>`);
        });

        return markup(formatted);
    }

    sendQuickAction(text) {
        this.state.promptText = text;
        this.onSendMessage();
    }

    onKeyDown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.onSendMessage();
        }
    }
}
