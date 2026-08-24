/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const CALL_PACKAGES = Object.freeze([
    {
        id: "starter",
        price: "$10",
        calls: "Unlimited",
        label: "Starter",
        url: "https://www.paypal.com/ncp/payment/9CCGLBAKUAR46",
    },
    {
        id: "growth",
        price: "$20",
        calls: "Unlimited",
        label: "Growth",
        url: "https://www.paypal.com/ncp/payment/77XHCYQR32VB2",
        featured: true,
    },
    {
        id: "business",
        price: "$80",
        calls: "Unlimited",
        label: "Business",
        url: "https://www.paypal.com/ncp/payment/Y77RLPSJT29VS",
    },
]);

export class BillingDashboard extends Component {
    static template = "twilio_dialer.BillingDashboard";
    static props = {
        "*": true,
    };

    setup() {

        this.notification = useService("notification");
        this.packages = CALL_PACKAGES;
        this.state = useState({ loading: true, error: "", billing: null });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await rpc("/twilio_dialer/billing");
            if (!result.success) {
                this.state.error = result.message || "Unable to load billing information.";
                return;
            }
            this.state.billing = result.billing;
        } catch {
            this.state.error = "Billing service is unavailable. Please try again.";
        } finally {
            this.state.loading = false;
        }
    }

    openUrl(url) {
        if (url) {
            window.open(url, "_blank", "noopener,noreferrer");
        }
    }

    get progress() {
        const billing = this.state.billing;
        if (!billing || billing.limit === "Unlimited" || !billing.limit) {
            return 0;
        }
        return Math.min((billing.usage / billing.limit) * 100, 100);
    }

    get usageState() {
        const billing = this.state.billing;
        if (billing && billing.limit === "Unlimited") {
            return "healthy";
        }
        return this.progress >= 100 ? "over-limit" : this.progress >= 80 ? "warning" : "healthy";
    }
}

registry.category("actions").add("twilio_dialer.billing", BillingDashboard);
