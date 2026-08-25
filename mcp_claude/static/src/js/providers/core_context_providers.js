/** @odoo-module **/

import { aiContextProviderRegistry } from "@mcp_claude/js/registries/ai_context_provider_registry";
import { user } from "@web/core/user";

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
            user_name: user ? user.name : null,
            user_id: user ? user.userId : null,
        };
    }
});
