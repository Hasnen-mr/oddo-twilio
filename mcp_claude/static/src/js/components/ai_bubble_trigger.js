/** @odoo-module **/

import { Component } from "@odoo/owl";

export class AIBubbleTrigger extends Component {
    static template = "mcp_claude.AIBubbleTrigger";
    static props = {
        isOpen: { type: Boolean },
        onClick: { type: Function },
        onDismiss: { type: Function, optional: true },
    };
}
