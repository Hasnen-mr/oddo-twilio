/** @odoo-module **/

import { onMounted } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const SCROLL_TOP_FORMS = ["o_dup_dashboard_form", "o_dup_hub_form", "o_dup_about_form"];

function usesScrollTopForm(rootEl) {
    if (!rootEl) {
        return false;
    }
    return SCROLL_TOP_FORMS.some(
        (className) =>
            rootEl.classList.contains(className) || Boolean(rootEl.querySelector(`.${className}`))
    );
}

function scrollActionToTop(rootEl) {
    const scrollers = new Set();
    let node = rootEl;
    while (node) {
        if (node.classList?.contains("o_content")) {
            scrollers.add(node);
        }
        node = node.parentElement;
    }
    for (const content of document.querySelectorAll(".o_action_manager .o_content")) {
        scrollers.add(content);
    }
    for (const content of scrollers) {
        content.scrollTop = 0;
    }
}

function resetScrollPosition(rootEl) {
    scrollActionToTop(rootEl);
    requestAnimationFrame(() => scrollActionToTop(rootEl));
}

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            const rootEl = this.rootRef?.el;
            if (!usesScrollTopForm(rootEl)) {
                return;
            }
            resetScrollPosition(rootEl);
        });
    },
});
