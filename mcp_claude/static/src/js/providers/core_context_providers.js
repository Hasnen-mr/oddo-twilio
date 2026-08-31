/** @odoo-module **/

import { aiContextProviderRegistry } from "@mcp_claude/js/registries/ai_context_provider_registry";
import { session } from "@web/session";

aiContextProviderRegistry.add("action_provider", {
    name: "Action & Controller Provider",
    priority: 10,
    enabled: true,
    merge_strategy: "override",
    extractContext(env, actionService) {
        if (!actionService || !actionService.currentController) {
            return null;
        }
        const controller = actionService.currentController;
        const props = controller.props || {};
        return {
            resModel: props.resModel || null,
            resId: props.resId || null,
            viewType: props.viewType || null,
            title: controller.title || null,
            selectedIds: controller.model && controller.model.root && controller.model.root.selection ? controller.model.root.selection.map(r => r.resId) : [],
        };
    }
});

aiContextProviderRegistry.add("user_company_provider", {
    name: "User & Company Context Provider",
    priority: 5,
    enabled: true,
    merge_strategy: "append",
    extractContext(env, actionService, userService) {
        return {
            user_name: session.name || session.userName || (userService ? userService.name : null),
            user_id: session.userId || session.uid || (userService ? userService.userId : null),
            partner_id: session.partnerId || null,
            company_id: session.companyId || (session.user_context && session.user_context.allowed_company_ids ? session.user_context.allowed_company_ids[0] : null),
            lang: session.user_context ? session.user_context.lang : (session.lang || "en_US"),
            tz: session.user_context ? session.user_context.tz : (session.tz || "UTC"),
        };
    }
});
