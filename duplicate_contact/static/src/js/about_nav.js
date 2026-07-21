/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

const SECTIONS = [
    { id: "overview", label: _t("About Module"), icon: "fa-info-circle" },
    { id: "how_it_works", label: _t("How It Works"), icon: "fa-cogs" },
    { id: "help", label: _t("Help"), icon: "fa-life-ring" },
    { id: "terms", label: _t("Terms & Privacy"), icon: "fa-file-text-o" },
];

export class DuplicateAboutNav extends Component {
    static template = "duplicate_contact.DuplicateAboutNav";
    static props = { ...standardFieldProps };

    setup() {
        this.rootRef = useRef("root");
        onMounted(() => this._applyShellLayout());
        onWillUnmount(() => this._clearShellLayout());
    }

    get sections() {
        return SECTIONS;
    }

    get activeSection() {
        return this.props.record.data.about_section || "overview";
    }

    isActive(section) {
        return this.activeSection === section.id;
    }

    async selectSection(section) {
        if (this.isActive(section)) {
            return;
        }
        await this.props.record.update({ about_section: section.id });
    }

    _findShell() {
        return this.rootRef.el?.closest(".o_dup_about_form") || null;
    }

    _applyShellLayout() {
        const shell = this._findShell();
        if (!shell) {
            return;
        }
        shell.classList.add("o_dup_about_shell");
        const host =
            this.rootRef.el.closest(".o_cell") ||
            this.rootRef.el.closest(".o_wrap_field") ||
            this.rootRef.el.parentElement;
        if (host) {
            host.classList.add("o_dup_about_nav_host");
        }
    }

    _clearShellLayout() {
        this._findShell()?.classList.remove("o_dup_about_shell");
        document.querySelectorAll(".o_dup_about_nav_host").forEach((el) => {
            el.classList.remove("o_dup_about_nav_host");
        });
    }
}

export const duplicateAboutNav = {
    component: DuplicateAboutNav,
    supportedTypes: ["char"],
};

registry.category("fields").add("duplicate_about_nav", duplicateAboutNav);
