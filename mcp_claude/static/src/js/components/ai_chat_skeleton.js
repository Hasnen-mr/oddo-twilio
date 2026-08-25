/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class AIChatSkeleton extends Component {
    static template = "mcp_claude.AIChatSkeleton";
    static props = {
        count: { type: Number, optional: true },
        isOverlay: { type: Boolean, optional: true },
    };

    setup() {
        const bubbleCount = this.props.count || Math.floor(Math.random() * 4) + 4; // 4 to 7 placeholders
        
        // Generate randomized realistic placeholders (widths 40% - 85%)
        this.placeholders = Array.from({ length: bubbleCount }, (_, i) => ({
            id: i,
            role: i % 2 === 0 ? "assistant" : "user",
            width: `${Math.floor(Math.random() * 45) + 40}%`,
            lines: i % 2 === 0 ? Math.floor(Math.random() * 2) + 1 : 1,
        }));
    }
}
