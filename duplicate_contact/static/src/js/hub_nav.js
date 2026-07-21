/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const SECTIONS = [
    { id: "merge_history", label: _t("Merge History"), icon: "fa-history" },
    { id: "scan_reports", label: _t("Scan Reports"), icon: "fa-bar-chart" },
    { id: "settings", label: _t("Settings"), icon: "fa-cog", adminOnly: true },
];

export class DuplicateHubNav extends Component {
    static template = "duplicate_contact.DuplicateHubNav";
    static props = { ...standardFieldProps };

    setup() {
        this.rootRef = useRef("root");
        this.action = useService("action");
        this.orm = useService("orm");
        onMounted(() => this._applyShellLayout());
        onWillUnmount(() => this._clearShellLayout());
    }

    get sections() {
        const isAdmin = this.props.record.data.is_settings_user;
        return SECTIONS.filter((section) => !section.adminOnly || isAdmin);
    }

    get activeSection() {
        return this.props.record.data.hub_section || "merge_history";
    }

    isActive(section) {
        return this.activeSection === section.id;
    }

    async selectSection(section) {
        if (this.isActive(section)) {
            return;
        }
        await this.props.record.update({ hub_section: section.id });
    }

    async goToDashboard() {
        const action = await this.orm.call(
            "duplicate.contact.hub",
            "action_back_to_dashboard",
            [],
        );
        this.action.doAction(action);
    }

    _findShell() {
        return this.rootRef.el?.closest(".o_dup_hub_form") || null;
    }

    _applyShellLayout() {
        const shell = this._findShell();
        if (!shell) {
            return;
        }
        shell.classList.add("o_dup_hub_shell");
        const host =
            this.rootRef.el.closest(".o_cell") ||
            this.rootRef.el.closest(".o_wrap_field") ||
            this.rootRef.el.parentElement;
        if (host) {
            host.classList.add("o_dup_hub_nav_host");
        }
    }

    _clearShellLayout() {
        this._findShell()?.classList.remove("o_dup_hub_shell");
        document.querySelectorAll(".o_dup_hub_nav_host").forEach((el) => {
            el.classList.remove("o_dup_hub_nav_host");
        });
    }
}

export const duplicateHubNav = {
    component: DuplicateHubNav,
    supportedTypes: ["char"],
};

registry.category("fields").add("duplicate_hub_nav", duplicateHubNav);
