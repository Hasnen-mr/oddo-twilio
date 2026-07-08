// async function loadCallLogs(){

//     const logs = await odoo.rpc({
//         route: "/twilio/get_call_logs",
//         params: {}
//     });

//     console.log(logs);
// }

odoo.define('twilio_dialer.call_timer', [], function (require) {
"use strict";

let timerRunning = false;

document.addEventListener("click", function (e) {

    const btn = e.target.closest(".call-btn-timer");

    if (!btn || timerRunning || btn.dataset.skipTimer) {
        return;
    }

    e.preventDefault();

    const timerBox = document.getElementById("call-timer");
    const timerText = document.getElementById("timer-count");

    if (!timerBox || !timerText) {
        return;
    }

    timerRunning = true;

    timerBox.style.display = "block";

    let count = 3;
    timerText.innerText = count;

    const interval = setInterval(function () {

        count--;
        timerText.innerText = count;

        if (count <= 0) {

            clearInterval(interval);

            timerBox.style.display = "none";

            timerRunning = false;

            btn.dataset.skipTimer = "true";
            btn.click();

        }

    }, 1000);

});

});