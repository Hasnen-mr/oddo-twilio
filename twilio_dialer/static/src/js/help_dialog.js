/** @odoo-module **/

import { Component } from "@odoo/owl";
import * as owl from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { Dialog } from "@web/core/dialog/dialog";

export class TwilioHelpDialog extends Component {
    static template = "twilio_dialer.TwilioHelpDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onOpenDialer: { type: Function, optional: true },
        onOpenTroubleshooter: { type: Function, optional: true },
        onOpenConfig: { type: Function, optional: true },
        onOpenAboutHelp: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            activeCategory: "make_call",
        });
    }

    setCategory(categoryId) {
        this.state.activeCategory = categoryId;
    }

    openDialer() {
        if (this.props.onOpenDialer) {
            this.props.onOpenDialer();
        }
        this.props.close();
    }

    openTroubleshooter() {
        if (this.props.onOpenTroubleshooter) {
            this.props.onOpenTroubleshooter();
        } else if (this.props.onOpenDialer) {
            this.props.onOpenDialer();
        }
        this.props.close();
    }

    openConfig() {
        if (this.props.onOpenConfig) {
            this.props.onOpenConfig();
        }
        this.props.close();
    }

    openAboutHelp() {
        if (this.props.onOpenAboutHelp) {
            this.props.onOpenAboutHelp();
        }
        this.props.close();
    }
}
