/** @odoo-module **/

import { whenReady } from "@odoo/owl";

const CHROME_STORE_URL = "https://bit.ly/odoo-twilio-dialer";
const TWILIO_DIALER_NUMBER = "+12345678900";
const TEL_DECORATED_SELECTOR = '[data-twilio-softphone-tel-decorated="1"]';

function isExtensionPresent() {
    return (
        document.documentElement.getAttribute("data-twilio-extension-ready") ===
            "1" || Boolean(document.querySelector(TEL_DECORATED_SELECTOR))
    );
}

function openChromeStore() {
    window.open(CHROME_STORE_URL, "_blank", "noopener,noreferrer");
}

function interceptActionButtons() {
    document.body.addEventListener(
        "click",
        (e) => {
            const openDialerBtn = e.target.closest('[data-twilio-open-sidepanel="1"]');
            if (openDialerBtn && !isExtensionPresent()) {
                e.preventDefault();
                e.stopPropagation();
                openChromeStore();
                return;
            }

            const callBtn = e.target.closest("#call-btn");
            if (!callBtn) {
                return;
            }
            if (!isExtensionPresent()) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                openChromeStore();
            }
        },
        true
    );
}

function toggleInlineUi(extensionPresent) {
    document.querySelectorAll(".twilio-config-install-btn").forEach((el) => {
        el.style.display = extensionPresent ? "none" : "inline-flex";
    });
    document.querySelectorAll(".twilio-config-dialer-btn").forEach((el) => {
        el.style.display = extensionPresent ? "inline-flex" : "none";
    });
    document.querySelectorAll(".twilio-dialer-install-panel").forEach((el) => {
        el.style.display = extensionPresent ? "none" : "flex";
    });
    document.querySelectorAll(".twilio-dialer-phone-ui").forEach((el) => {
        el.style.display = extensionPresent ? "" : "none";
    });
}

function updateFloatingButtons(dialerBtn, chromeBtn) {
    const extensionPresent = isExtensionPresent();

    if (extensionPresent) {
        dialerBtn.style.display = "inline-flex";
        chromeBtn.style.display = "none";
    } else {
        dialerBtn.style.display = "none";
        chromeBtn.style.display = "inline-flex";
    }

    toggleInlineUi(extensionPresent);
}

whenReady(() => {
    const container = document.createElement("div");
    container.id = "twilio-softphone-floating";
    container.className = "twilio-softphone-floating";

    const dialerBtn = document.createElement("button");
    dialerBtn.type = "button";
    dialerBtn.title = "Open Dialer";
    dialerBtn.className = "twilio-open-dialer-btn";
    dialerBtn.setAttribute("data-twilio-open-sidepanel", "1");
    dialerBtn.setAttribute("data-twilio-dial-number", TWILIO_DIALER_NUMBER);
    dialerBtn.innerHTML = `<i class="fa fa-phone"></i><span>Open Dialer</span>`;

    const chromeBtn = document.createElement("a");
    chromeBtn.href = CHROME_STORE_URL;
    chromeBtn.target = "_blank";
    chromeBtn.rel = "noopener noreferrer";
    chromeBtn.className = "twilio-chrome-store-btn";
    chromeBtn.title = "Install Chrome Extension";
    chromeBtn.innerHTML = `<i class="fa fa-chrome"></i><span>Install Extension</span>`;

    container.appendChild(dialerBtn);
    container.appendChild(chromeBtn);
    document.body.appendChild(container);

    updateFloatingButtons(dialerBtn, chromeBtn);

    const observer = new MutationObserver(() => {
        updateFloatingButtons(dialerBtn, chromeBtn);
    });
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-twilio-extension-ready"],
    });
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-twilio-softphone-tel-decorated"],
    });

    interceptActionButtons();
});
