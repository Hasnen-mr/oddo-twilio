/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class AISystrayItem extends Component {
    static template = "mcp_claude.AISystrayItem";

    setup() {
        const activeTab = localStorage.getItem("mcp_active_tab") || "dashboard";
        this.state = useState({
            isHiddenOnClaude: activeTab === "claude",
        });

        this._onTabChange = (ev) => {
            const currentTab = (ev.detail && ev.detail.tab) || localStorage.getItem("mcp_active_tab");
            this.state.isHiddenOnClaude = (currentTab === "claude");
        };

        window.addEventListener("mcp_tab_changed", this._onTabChange);

        onWillUnmount(() => {
            window.removeEventListener("mcp_tab_changed", this._onTabChange);
        });
    }

    onSystrayClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        window.dispatchEvent(new CustomEvent("toggle_mcp_ai_window"));
    }
}

registry.category("systray").add("mcp_claude.AISystrayItem", {
    Component: AISystrayItem,
}, { sequence: 25 });
