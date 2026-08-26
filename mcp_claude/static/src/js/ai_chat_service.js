/** @odoo-module **/

import { aiContextProviderRegistry } from "@mcp_claude/js/registries/ai_context_provider_registry";
import { jsonrpc as rpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user_service";

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
                            const ctx = provider.extractContext(env, action, user);
                            if (ctx) {
                                Object.assign(contextPayload, ctx);
                            }
                        } catch (e) {
                            console.error("[AI Context Provider Error]", provider.name, e);
                        }
                    }
                }
                return contextPayload;
            },
            async initChat(scope = "global", modelName = null, resId = null, workspaceApp = null, signal = null) {
                try {
                    const validSessionId = parseValidId(activeSessionId);
                    const res = await rpc("/mcp/ai/v1/chat/init", {
                        session_id: validSessionId,
                        scope: "global",
                        model_name: null,
                        res_id: null,
                        workspace_app: null,
                    }, { signal });

                    if (res && res.success) {
                        activeSessionId = res.session_id;
                        activeConversationId = res.conversation_id;
                        localStorage.setItem("mcp_ai_session_id", activeSessionId);
                        localStorage.setItem("mcp_ai_conversation_id", activeConversationId);
                        return res;
                    }
                } catch (e) {
                    if (e && (e.name === "AbortError" || e.code === 20)) {
                        console.info("[AI Chat Init] In-flight RPC aborted gracefully.");
                        return { aborted: true };
                    }
                    console.error("[AI Chat Init Error]", e);
                }
                return null;
            },
            async sendMessage(prompt) {
                const validConvId = parseValidId(activeConversationId);
                if (!validConvId) {
                    await this.initChat();
                }
                const contextSnapshot = {};
                try {
                    const res = await rpc("/mcp/ai/v1/chat/message", {
                        conversation_id: parseValidId(activeConversationId),
                        prompt: prompt,
                        context_snapshot: contextSnapshot,
                    });
                    return res;
                } catch (e) {
                    notification.add(`AI Communication Error: ${e.message || e}`, { type: "danger" });
                    return { success: false, error: e.message };
                }
            }
        };
    }
};

registry.category("services").add("ai_chat_service", aiChatService);
