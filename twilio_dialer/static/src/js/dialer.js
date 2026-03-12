async function loadCallLogs(){

    const logs = await odoo.rpc({
        route: "/twilio/get_call_logs",
        params: {}
    });

    console.log(logs);
}