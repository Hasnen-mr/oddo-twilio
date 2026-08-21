/** @odoo-module **/

function activateAITab() {
    const aiTabHeader = document.querySelector('.nav-link[name="ai"], a[data-bs-target*="ai"]');
    if (aiTabHeader) {
        aiTabHeader.click();
    }
}

document.addEventListener("click", (ev) => {
    const link = ev.target.closest(".o_open_ai_tab");
    if (link) {
        const aiTabHeader = document.querySelector('.nav-link[name="ai"], a[data-bs-target*="ai"]');
        if (aiTabHeader) {
            ev.preventDefault();
            ev.stopPropagation();
            activateAITab();
        }
    }
});

// Activate tab if URL hash contains #ai_tab on page load
if (window.location.hash && window.location.hash.includes("ai_tab")) {
    window.addEventListener("DOMContentLoaded", () => {
        setTimeout(activateAITab, 300);
    });
}
