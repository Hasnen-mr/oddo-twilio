/** @odoo-module **/

import { registry } from "@web/core/registry";
import { VersionUpdateDialog } from "./version_update_dialog";

const CHECK_DELAY_MS = 2500;

export const twilioVersionUpdateService = {
    dependencies: ["orm", "dialog"],

    start(env, { orm, dialog }) {
        const runCheck = async () => {
            try {
                const info = await orm.call(
                    "twilio.version.update",
                    "check_for_update",
                    []
                );
                if (!info || !info.available) {
                    return;
                }
                dialog.add(VersionUpdateDialog, {
                    title: info.title,
                    message: info.message,
                    installed_version: info.installed_version,
                    latest_version: info.latest_version,
                    features: info.features || [],
                    download_url: info.download_url,
                    release_date: info.release_date,
                    onRemindLater: async () => {
                        await orm.call("twilio.version.update", "snooze_update", []);
                    },
                    onOkay: async () => {
                        await orm.call(
                            "twilio.version.update",
                            "dismiss_update",
                            [info.latest_version]
                        );
                    },
                });
            } catch (error) {
                // Silent: offline / no permission should not interrupt the UI
                console.debug("Twilio Dialer update check skipped:", error);
            }
        };

        // Run once after the web client has settled
        const timer = setTimeout(runCheck, CHECK_DELAY_MS);
        return {
            checkNow: runCheck,
            destroy() {
                clearTimeout(timer);
            },
        };
    },
};

registry
    .category("services")
    .add("twilio_version_update", twilioVersionUpdateService);
