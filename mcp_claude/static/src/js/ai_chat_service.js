/** @odoo-module **/

import { aiContextProviderRegistry } from "@mcp_claude/js/registries/ai_context_provider_registry";
import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

export const aiChatService = {
    dependencies: ["action", "notification"],
    start(env, { action, notification }) {
        let activeSessionId = localStorage.getItem("mcp_ai_session_id");
        let activeConversationId = localStorage.getItem("mcp_ai_conversation_id");

        // Helper to sanitize integer IDs from localStorage
        function parseValidId(val) {
            if (!val || val === "null" || val === "undefined") return null;
            const parsed = parseInt(val, 10);
            return isNaN(parsed) ? null : parsed;
        }

        return {
            getActiveSessionId() {
                return parseValidId(activeSessionId);
            },
            getActiveConversationId() {
                return parseValidId(activeConversationId);
            },
            collectActiveContext() {
                const contextPayload = {};
                const providers = aiContextProviderRegistry.getAll().sort((a, b) => (a.priority || 0) - (b.priority || 0));
                for (const provider of providers) {
                    if (provider.enabled && typeof provider.extractContext === "function") {
                        try {
                            const ctx = provider.extractContext(env, action, session);
                            if (ctx) {
                                Object.assign(contextPayload, ctx);
                            }
                        } catch (e) {
                            console.warn(`[MCP Claude Context] Provider ${provider.name} failed:`, e);
                        }
                    }
                }
                return contextPayload;
            },
            async initChat(scope = "global", resModel = null, resId = null, forcedConvId = null, signal = null) {
                try {
                    const ctx = this.collectActiveContext();
                    const body = {
                        scope,
                        res_model: resModel || ctx.resModel || null,
                        res_id: resId || ctx.resId || null,
                        session_id: this.getActiveSessionId(),
                        forced_conversation_id: forcedConvId || null,
                        context: ctx,
                    };

                    const res = await rpc("/mcp_claude/chat/init", body, { signal });
                    if (res && res.success) {
                        if (res.session_id) {
                            activeSessionId = String(res.session_id);
                            localStorage.setItem("mcp_ai_session_id", activeSessionId);
                        }
                        if (res.conversation_id) {
                            activeConversationId = String(res.conversation_id);
                            localStorage.setItem("mcp_ai_conversation_id", activeConversationId);
                        }
                    }
                    return res;
                } catch (error) {
                    if (error && error.name === "AbortError") {
                        return { success: false, aborted: true };
                    }
                    console.error("[MCP Claude InitChat RPC Error]", error);
                    return { success: false, error: error.message || "Failed to initialize conversation" };
                }
            },
            async sendMessage(prompt, options = {}) {
                try {
                    const ctx = this.collectActiveContext();
                    const body = {
                        session_id: this.getActiveSessionId(),
                        conversation_id: this.getActiveConversationId(),
                        prompt,
                        context: ctx,
                        ...options,
                    };
                    return await rpc("/mcp_claude/chat/message", body);
                } catch (error) {
                    console.error("[MCP Claude SendMessage RPC Error]", error);
                    return { success: false, error: error.message || "Failed to send message" };
                }
            }
        };
    },
};

registry.category("services").add("ai_chat_service", aiChatService);
