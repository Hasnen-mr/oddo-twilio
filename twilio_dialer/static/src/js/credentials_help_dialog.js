/** @odoo-module **/

import { Component } from "@odoo/owl";
import * as owl from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";

export class TwilioCredentialsHelpDialog extends Component {
    static template = "twilio_dialer.CredentialsHelpDialog";
    static components = { Dialog };
    static props = {
        close: Function,
    };

    setup() {
        this.state = useState({
            activeTab: "classic", // 'classic' or 'new'
        });
    }

    setTab(tabName) {
        this.state.activeTab = tabName;
    }
}

// Client action to invoke from Python (e.g., Configuration page)
registry.category("actions").add("twilio_dialer.action_credentials_help", (env) => {
    env.services.dialog.add(TwilioCredentialsHelpDialog);
}, { force: true });