/** @odoo-module **/

import { Component } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { DialerPopup } from "@twilio_dialer_pro/js/dialer_popup";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DialerSystray extends Component {
    static components = { DialerPopup };
    static template = "twilio_dialer_pro.DialerSystray";

    setup() {
        this.dialer = useService("twilio_dialer");
        this.state = useState(this.dialer.state);
    }

    togglePanel() {
        this.dialer.toggle();
    }

    closePanel() {
        this.dialer.close();
    }
}

registry
    .category("systray")
    .add(
        "twilio_dialer_pro.dialer_systray",
        { Component: DialerSystray },
        { sequence: 30, force: true }
    );
