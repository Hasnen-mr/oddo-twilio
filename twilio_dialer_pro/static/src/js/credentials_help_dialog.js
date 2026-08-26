/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TwilioCredentialsHelpDialog extends Component {
    static template = "twilio_dialer_pro.CredentialsHelpDialog";
    static components = { Dialog };
    static props = {
        close: Function,
    };

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            activeTab: "classic", // 'classic' or 'new'
        });
    }

    setTab(tabName) {
        this.state.activeTab = tabName;
    }
}

// Client action to invoke from Python (e.g., Configuration page)
registry.category("actions").add("twilio_dialer_pro.action_credentials_help", (env) => {
    env.services.dialog.add(TwilioCredentialsHelpDialog);
}, { force: true });