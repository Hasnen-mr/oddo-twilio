/** @odoo-module **/

import { Component, onWillUnmount, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const WATCHED_FIELDS = [
    "twilio_phone_number",
    "twilio_incoming_enabled",
    "twilio_incoming_record",
    "twilio_incoming_transcription",
    "twilio_incoming_voicemail",
    "twilio_incoming_voicemail_text",
    "twilio_incoming_forward",
    "twilio_incoming_forward_to",
    "twilio_outgoing_record",
    "twilio_outgoing_transcription",
    "twilio_outgoing_smart_copy",
];

const TEXT_FIELDS = new Set([
    "twilio_incoming_voicemail_text",
    "twilio_incoming_forward_to",
]);

function snapshotCallSettings(data) {
    const snap = {};
    for (const name of WATCHED_FIELDS) {
        snap[name] = data[name];
    }
    snap.twilio_account_sid = data.twilio_account_sid;
    return snap;
}

function snapshotsEqual(a, b) {
    if (!a || !b) {
        return false;
    }
    return WATCHED_FIELDS.every((name) => a[name] === b[name]);
}

function changedFields(prev, next) {
    if (!prev) {
        return WATCHED_FIELDS.slice();
    }
    return WATCHED_FIELDS.filter((name) => prev[name] !== next[name]);
}

export class CallSettingsAutosave extends Component {
    static template = "twilio_dialer.CallSettingsAutosave";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this._ready = false;
        this._saving = false;
        this._lastSaved = null;
        this._pending = null;
        this._timer = null;
        this._seq = 0;
        this._prevVoicemail = false;
        this._prevForward = false;

        useEffect(
            () => {
                const data = this.props.record.data;
                if (data.twilio_config_section && data.twilio_config_section !== "call") {
                    return;
                }
                if (!data.twilio_is_connected) {
                    return;
                }

                const voicemail = data.twilio_incoming_voicemail;
                const forward = data.twilio_incoming_forward;

                if (voicemail && forward) {
                    const voicemailJustTurnedOn = voicemail && !this._prevVoicemail;
                    const forwardJustTurnedOn = forward && !this._prevForward;

                    if (voicemailJustTurnedOn && forwardJustTurnedOn) {
                        this.props.record.update({
                            twilio_incoming_forward: false,
                            twilio_incoming_forward_to: "",
                        });
                        this._prevVoicemail = true;
                        this._prevForward = false;
                    } else if (forwardJustTurnedOn) {
                        this.props.record.update({
                            twilio_incoming_voicemail: false,
                            twilio_incoming_voicemail_text: "",
                        });
                        this._prevVoicemail = false;
                        this._prevForward = true;
                    } else {
                        this.props.record.update({
                            twilio_incoming_forward: false,
                            twilio_incoming_forward_to: "",
                        });
                        this._prevVoicemail = true;
                        this._prevForward = false;
                    }
                    return;
                }

                this._prevVoicemail = voicemail;
                this._prevForward = forward;

                const snap = snapshotCallSettings(data);
                if (!this._ready) {
                    this._lastSaved = snap;
                    this._ready = true;
                    return;
                }
                if (snapshotsEqual(snap, this._lastSaved) || snapshotsEqual(snap, this._pending)) {
                    return;
                }

                const changed = changedFields(this._lastSaved, snap);
                const delay = changed.some((name) => TEXT_FIELDS.has(name)) ? 650 : 180;
                this._pending = snap;
                clearTimeout(this._timer);
                this._timer = setTimeout(() => this._save(snap), delay);
            },
            () => [
                this.props.record.data.twilio_config_section,
                this.props.record.data.twilio_is_connected,
                ...WATCHED_FIELDS.map((name) => this.props.record.data[name]),
            ]
        );

        onWillUnmount(() => {
            clearTimeout(this._timer);
        });
    }

    async _save(snap) {
        if (this._saving) {
            this._pending = snap;
            clearTimeout(this._timer);
            this._timer = setTimeout(() => this._save(snap), 200);
            return;
        }
        if (snapshotsEqual(snap, this._lastSaved)) {
            this._pending = null;
            return;
        }

        this._saving = true;
        const seq = ++this._seq;
        try {
            const result = await this.orm.call(
                "res.config.settings",
                "autosave_call_settings",
                [snap]
            );
            if (seq !== this._seq) {
                return;
            }
            if (!result?.success) {
                this.notification.add(result?.message || _t("Unable to update call settings."), {
                    type: "danger",
                });
                return;
            }
            this._lastSaved = snap;
            this._pending = null;
            this.notification.add(_t("Settings updated successfully."), {
                type: "success",
            });
        } catch {
            if (seq === this._seq) {
                this.notification.add(_t("Unable to update call settings."), {
                    type: "danger",
                });
            }
        } finally {
            this._saving = false;
            if (this._pending && !snapshotsEqual(this._pending, this._lastSaved)) {
                const pending = this._pending;
                clearTimeout(this._timer);
                this._timer = setTimeout(() => this._save(pending), 150);
            }
        }
    }
}

export const callSettingsAutosave = {
    component: CallSettingsAutosave,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_call_settings_autosave", callSettingsAutosave);
