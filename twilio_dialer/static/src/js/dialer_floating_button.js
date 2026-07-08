/** @odoo-module **/

import { whenReady } from "@odoo/owl";

whenReady(() => {
    const btn = document.createElement("button");

    btn.innerHTML = `<i class="fa fa-phone"></i>`;

    Object.assign(btn.style, {
        position: "fixed",
        bottom: "20px",
        right: "20px",
        width: "60px",
        height: "60px",
        borderRadius: "50%",
        background: "#25D366",
        color: "white",
        border: "none",
        fontSize: "22px",
        cursor: "pointer",
        zIndex: "9999",
    });

    btn.addEventListener("click", () => {
        // 🔥 direct client action
        window.location.href = "/web#action=twilio_dialer.action_click_to_call_wizard";
    });

    document.body.appendChild(btn);
});

// /** @odoo-module **/

// import { whenReady } from "@odoo/owl";

// whenReady(() => {
//     console.log("JS Loaded 🔥");

//     // Create Floating Call Button
//     const btn = document.createElement("button");

//     btn.innerHTML = `<i class="fa fa-phone"></i>`;
//     btn.title = "Open Dialer";

//     // Styling
//     btn.style.position = "fixed";
//     btn.style.bottom = "20px";
//     btn.style.right = "20px";
//     btn.style.width = "60px";
//     btn.style.height = "60px";
//     btn.style.borderRadius = "50%";
//     btn.style.background = "#25D366";
//     btn.style.color = "white";
//     btn.style.border = "none";
//     btn.style.fontSize = "22px";
//     btn.style.cursor = "pointer";
//     btn.style.zIndex = "9999";
//     btn.style.display = "flex";
//     btn.style.alignItems = "center";
//     btn.style.justifyContent = "center";
//     btn.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";

//     // Click Event
//     btn.addEventListener("click", () => {
//         alert("Dialer Open"); // ya action call laga sakta hai
//     });

//     document.body.appendChild(btn);
// });