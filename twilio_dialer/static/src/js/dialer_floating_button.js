/** @odoo-module **/

import { Component, useService } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class TwilioDialerFloatingButton extends Component {
    setup() {
        this.actionService = useService("action");
    }

    openDialer() {
        if (this.actionService) {
            this.actionService.doAction("twilio_dialer.action_click_to_call_wizard");
        }
    }
}

TwilioDialerFloatingButton.template = "twilio_dialer.TwilioDialerFloatingButton";

const webClientComponents = registry.category("webclient_components");

if (!webClientComponents.contains("TwilioDialerFloatingButton")) {
    webClientComponents.add("TwilioDialerFloatingButton", {
        Component: TwilioDialerFloatingButton,
        props: {},
    });
}

