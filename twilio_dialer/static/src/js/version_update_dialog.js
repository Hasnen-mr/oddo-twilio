/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class VersionUpdateDialog extends Component {
    static template = "twilio_dialer.VersionUpdateDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        message: { type: String, optional: true },
        installed_version: { type: String, optional: true },
        latest_version: { type: String, optional: true },
        features: { type: Array, optional: true },
        download_url: { type: String, optional: true },
        release_date: { type: String, optional: true },
        onRemindLater: { type: Function, optional: true },
        onOkay: { type: Function, optional: true },
    };

    get dialogTitle() {
        return this.props.title || _t("New Version Available");
    }

    get features() {
        return this.props.features || [];
    }

    async onRemindLater() {
        if (this.props.onRemindLater) {
            await this.props.onRemindLater();
        }
        this.props.close();
    }

    async onOkay() {
        if (this.props.onOkay) {
            await this.props.onOkay();
        }
        this.props.close();
    }

    openDownload() {
        const url = this.props.download_url;
        if (url) {
            window.open(url, "_blank", "noopener,noreferrer");
        }
    }
}
