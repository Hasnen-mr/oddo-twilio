/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

class BillingDashboard extends Component {
    static template = "twilio_dialer.BillingDashboard";

    setup() {
        this.notification = useService("notification");
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
        return billing?.limit ? Math.min((billing.usage / billing.limit) * 100, 100) : 0;
    }

    get usageState() {
        return this.progress >= 100 ? "over-limit" : this.progress >= 80 ? "warning" : "healthy";
    }

    get maskedAccountSid() {
        const sid = this.state.billing?.accountSid || "";
        return sid.length > 10 ? `${sid.slice(0, 4)}••••••••${sid.slice(-4)}` : sid;
    }

    get purchaseHistory() {
        return Array.isArray(this.state.billing?.purchaseHistory) ? this.state.billing.purchaseHistory : [];
    }

    get activity() {
        return Array.isArray(this.state.billing?.activity) ? this.state.billing.activity : [];
    }
}

registry.category("actions").add("twilio_dialer.billing", BillingDashboard);
