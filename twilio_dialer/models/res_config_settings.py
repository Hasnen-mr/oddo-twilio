# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services import MyBroadcastAPI, MyBroadcastAPIError, ZantaTechAPI, ZantaTechAPIError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Left-sidebar section on Configuration page (client-only, not persisted)
    twilio_config_section = fields.Selection(
        selection=[
            ("call", "Call Settings"),
            ("ai", "AI Settings"),
            ("account", "Account Setting"),
            ("billing", "Billing"),
        ],
        string="Configuration Section",
        default="call",
    )
    twilio_billing_panel = fields.Char(
        string="Billing Panel",
        default="1",
    )

    # ── Account Details ───────────────────────────────────
    twilio_account_sid = fields.Char(
        string="Account SID",
        config_parameter="twilio_dialer.account_sid",
    )
    twilio_auth_token = fields.Char(
        string="Auth Token",
        config_parameter="twilio_dialer.auth_token",
    )
    twilio_contact_email = fields.Char(
        string="Contact Email",
        config_parameter="twilio_dialer.contact_email",
        help="Email used for module registration and support notifications.",
    )
    twilio_contact_phone = fields.Char(
        string="Contact Phone",
        config_parameter="twilio_dialer.contact_phone",
    )
    twilio_phone_number = fields.Selection(
        string="Twilio Phone Number",
        selection="_get_twilio_phone_number_selection",
        help="Select the Twilio Incoming Phone Number used as the outbound caller ID.",
        config_parameter="twilio_dialer.phone_number",
    )
    twilio_api_key_sid = fields.Char(
        string="API Key SID",
        readonly=True,
        config_parameter="twilio_dialer.api_key_sid",
    )
    twilio_api_secret = fields.Char(
        string="API Secret",
        readonly=True,
        config_parameter="twilio_dialer.api_secret",
    )
    twilio_application_sid = fields.Char(
        string="Application SID",
        readonly=True,
        config_parameter="twilio_dialer.application_sid",
    )
    twilio_voice_url = fields.Char(
        string="Voice URL",
        compute="_compute_twilio_voice_url",
        readonly=True,
    )
    twilio_status = fields.Char(
        string="Status",
        compute="_compute_twilio_status",
        readonly=True,
    )
    twilio_is_connected = fields.Boolean(
        string="Twilio Connected",
        compute="_compute_twilio_status",
        readonly=True,
    )

    # ── Call Settings ─────────────────────────────────────
    twilio_incoming_enabled = fields.Boolean(
        string="Enable Incoming Calls",
    )
    twilio_incoming_record = fields.Boolean(
        string="Record Incoming Calls",
    )
    twilio_incoming_voicemail = fields.Boolean(
        string="Send Unanswered to Voicemail",
    )
    twilio_incoming_voicemail_text = fields.Text(
        string="Voicemail Text",
    )
    twilio_incoming_forward = fields.Boolean(
        string="Forward Calls",
    )
    twilio_incoming_forward_to = fields.Char(
        string="Forward To",
    )
    twilio_outgoing_record = fields.Boolean(
        string="Record Outgoing Calls",
    )
    twilio_outgoing_smart_copy = fields.Boolean(
        string="Smart Copy",
    )
    twilio_call_settings_error = fields.Char(readonly=True)
    twilio_call_settings_autosave = fields.Char(
        string="Call Settings Autosave",
        default="1",
    )

    # ── AI Settings ───────────────────────────────────────
    twilio_ai_provider = fields.Selection(
        selection=[
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("gemini", "Google Gemini"),
            ("deepgram", "Deepgram"),
        ],
        string="Default AI Provider",
        config_parameter="twilio_dialer.ai_provider",
        default="openai",
    )
    twilio_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter="twilio_dialer.openai_api_key",
    )
    twilio_anthropic_api_key = fields.Char(
        string="Anthropic API Key",
        config_parameter="twilio_dialer.anthropic_api_key",
    )
    twilio_gemini_api_key = fields.Char(
        string="Google Gemini API Key",
        config_parameter="twilio_dialer.gemini_api_key",
    )
    twilio_deepgram_api_key = fields.Char(
        string="Deepgram API Key",
        config_parameter="twilio_dialer.deepgram_api_key",
    )
    twilio_ai_enable_transcript = fields.Boolean(
        string="Create Call Transcripts",
        config_parameter="twilio_dialer.ai_enable_transcript",
        default=False,
    )
    twilio_ai_enable_summary = fields.Boolean(
        string="Create Call Summaries",
        config_parameter="twilio_dialer.ai_enable_summary",
        default=False,
    )
    twilio_ai_auto_on_complete = fields.Boolean(
        string="Auto Generate on Call Complete",
        config_parameter="twilio_dialer.ai_auto_on_complete",
        default=False,
        help="When enabled, transcript/summary are generated automatically after a completed call (when recording or notes are available).",
    )

    @api.depends("twilio_api_key_sid", "twilio_application_sid")
    def _compute_twilio_status(self):
        for record in self:
            connected = bool(record.twilio_api_key_sid and record.twilio_application_sid)
            record.twilio_is_connected = connected
            record.twilio_status = "Connected" if connected else "Not Configured"

    def _compute_twilio_voice_url(self):
        """Always show the Smart Tools Voice URL in Configuration."""
        voice_url = self.env["twilio.service"].get_voice_url(self.env)
        for record in self:
            record.twilio_voice_url = voice_url

    @staticmethod
    def _call_settings_section(settings, names, label, errors):
        """Return the first valid API section without assuming its response shape."""
        for name in names:
            value = settings.get(name)
            if value is None:
                continue
            if isinstance(value, dict):
                return value
            _logger.warning(
                "MyBroadcast returned an invalid %s Call Settings section (%s): %r",
                label,
                type(value).__name__,
                value,
            )
            errors.append(label)
        return {}

    def _parse_call_settings(self, payload):
        """Validate API payload sections before reading their settings values."""
        if not isinstance(payload, dict):
            _logger.warning("MyBroadcast returned a non-object Call Settings payload: %r", payload)
            return {}, {}, "Call settings service returned an invalid response."

        nested_settings = payload.get("settings")
        if nested_settings is None:
            settings = payload
        elif isinstance(nested_settings, dict):
            settings = nested_settings
        else:
            _logger.warning(
                "MyBroadcast returned an invalid settings container (%s): %r",
                type(nested_settings).__name__,
                nested_settings,
            )
            return {}, {}, "Call settings service returned invalid settings data."

        errors = []
        incoming = self._call_settings_section(
            settings,
            ("incomingCallSetting", "incoming"),
            "incoming",
            errors,
        )
        outgoing = self._call_settings_section(
            settings,
            ("outgoingCallSetting", "outgoing"),
            "outgoing",
            errors,
        )
        if errors:
            return incoming, outgoing, "Call settings service returned invalid %s data." % (
                " and ".join(sorted(set(errors)))
            )
        return incoming, outgoing, False

    @staticmethod
    def _call_settings_values(incoming, outgoing):
        """Map validated API sections to transient fields only."""
        return {
            "twilio_incoming_enabled": incoming.get("allow"),
            "twilio_incoming_record": incoming.get("record"),
            "twilio_incoming_voicemail": incoming.get("voicemail"),
            "twilio_incoming_voicemail_text": incoming.get("voicemailText", ""),
            "twilio_incoming_forward": incoming.get("forward"),
            "twilio_incoming_forward_to": incoming.get("forwardTo", ""),
            "twilio_outgoing_record": outgoing.get("record"),
            "twilio_outgoing_smart_copy": outgoing.get("smartCopy"),
        }

    @api.model
    def get_values(self):
        values = super().get_values()
        connected = bool(
            values.get("twilio_api_key_sid") and values.get("twilio_application_sid")
        )
        values["twilio_config_section"] = "call" if connected else "account"

        account_sid = self.env["ir.config_parameter"].sudo().get_param(
            "twilio_dialer.account_sid"
        )
        if not account_sid:
            return values

        try:
            payload = MyBroadcastAPI().get_call_settings(account_sid)
            incoming, outgoing, error = self._parse_call_settings(payload)
            if error:
                values["twilio_call_settings_error"] = error
            else:
                values.update(self._call_settings_values(incoming, outgoing))
        except MyBroadcastAPIError as error:
            _logger.warning("Unable to load MyBroadcast call settings: %s", error)
            values["twilio_call_settings_error"] = str(error)
        return values

    def action_save_call_settings(self):
        self.ensure_one()
        result = self.autosave_call_settings({
            "twilio_account_sid": self.twilio_account_sid,
            "twilio_phone_number": self.twilio_phone_number,
            "twilio_incoming_enabled": self.twilio_incoming_enabled,
            "twilio_incoming_record": self.twilio_incoming_record,
            "twilio_incoming_voicemail": self.twilio_incoming_voicemail,
            "twilio_incoming_voicemail_text": self.twilio_incoming_voicemail_text or "",
            "twilio_incoming_forward": self.twilio_incoming_forward,
            "twilio_incoming_forward_to": self.twilio_incoming_forward_to or "",
            "twilio_outgoing_record": self.twilio_outgoing_record,
            "twilio_outgoing_smart_copy": self.twilio_outgoing_smart_copy,
        })
        notif_type = "success" if result.get("success") else "danger"
        if result.get("success"):
            incoming = result.get("incoming") or {}
            outgoing = result.get("outgoing") or {}
            if incoming or outgoing:
                self.update(self._call_settings_values(incoming, outgoing))
        return self._reload_twilio_settings(
            "Call Settings",
            result.get("message") or "Settings updated successfully.",
            notif_type,
        )

    @api.model
    def autosave_call_settings(self, values):
        """Persist Call Settings immediately (no Save button / no page reload)."""
        values = values or {}
        account_sid = (
            values.get("twilio_account_sid")
            or self.env["ir.config_parameter"].sudo().get_param("twilio_dialer.account_sid")
        )
        if not account_sid:
            return {
                "success": False,
                "message": "Configure and save a Twilio Account SID before updating call settings.",
            }

        phone_number = values.get("twilio_phone_number")
        if phone_number:
            try:
                phone_number = self.env["twilio.service"].validate_phone_number(phone_number)
                self.env["ir.config_parameter"].sudo().set_param(
                    "twilio_dialer.phone_number",
                    phone_number,
                )
            except UserError as error:
                return {"success": False, "message": str(error)}

        settings = {
            "incomingCallSetting": {
                "allow": bool(values.get("twilio_incoming_enabled")),
                "record": bool(values.get("twilio_incoming_record")),
                "voicemail": bool(values.get("twilio_incoming_voicemail")),
                "voicemailText": values.get("twilio_incoming_voicemail_text") or "",
                "forward": bool(values.get("twilio_incoming_forward")),
                "forwardTo": values.get("twilio_incoming_forward_to") or "",
            },
            "outgoingCallSetting": {
                "record": bool(values.get("twilio_outgoing_record")),
                "smartCopy": bool(values.get("twilio_outgoing_smart_copy")),
            },
        }
        try:
            payload = MyBroadcastAPI().save_call_settings(account_sid, settings)
        except MyBroadcastAPIError as error:
            return {"success": False, "message": str(error)}

        incoming, outgoing, error = self._parse_call_settings(payload)
        if error:
            _logger.warning(
                "MyBroadcast returned malformed Call Settings after autosave: %s",
                error,
            )
            return {"success": False, "message": error}

        return {
            "success": True,
            "message": "Settings updated successfully.",
            "incoming": incoming,
            "outgoing": outgoing,
        }

    @api.model
    def _get_twilio_phone_number_selection(self):
        phone_numbers = self.env["ir.config_parameter"].sudo().get_param(
            "twilio_dialer.incoming_phone_numbers",
            "[]",
        )
        try:
            phone_numbers = json.loads(phone_numbers)
        except json.JSONDecodeError:
            return []

        return [
            (
                number["phone_number"],
                f"{number['friendly_name']} ({number['phone_number']})"
                if number.get("friendly_name")
                else number["phone_number"],
            )
            for number in phone_numbers
        ]

    @api.constrains("twilio_phone_number")
    def _check_twilio_phone_number(self):
        for record in self:
            if record.twilio_phone_number:
                self.env["twilio.service"].validate_phone_number(
                    record.twilio_phone_number
                )

    def _twilio_preserve_generated_fields(self):
        """Keep existing generated credentials when the settings form shows them empty."""
        icp = self.env["ir.config_parameter"].sudo()
        for record in self:
            if not record.twilio_api_key_sid:
                record.twilio_api_key_sid = icp.get_param("twilio_dialer.api_key_sid") or False
            if not record.twilio_api_secret:
                record.twilio_api_secret = icp.get_param("twilio_dialer.api_secret") or False
            if not record.twilio_application_sid:
                record.twilio_application_sid = (
                    icp.get_param("twilio_dialer.application_sid") or False
                )

    def _twilio_should_auto_generate(self):
        """True when credentials are present and connection setup is incomplete or changed."""
        self.ensure_one()
        if not self.twilio_account_sid or not self.twilio_auth_token:
            return False

        icp = self.env["ir.config_parameter"].sudo()
        stored_sid = icp.get_param("twilio_dialer.account_sid") or ""
        stored_token = icp.get_param("twilio_dialer.auth_token") or ""
        creds_changed = (
            self.twilio_account_sid != stored_sid
            or self.twilio_auth_token != stored_token
        )

        phone_raw = icp.get_param("twilio_dialer.incoming_phone_numbers", "[]")
        try:
            phone_list = json.loads(phone_raw)
        except json.JSONDecodeError:
            phone_list = []

        incomplete = not (
            self.twilio_api_key_sid
            and self.twilio_api_secret
            and self.twilio_application_sid
            and phone_list
        )
        return creds_changed or incomplete

    def _generate_twilio_configuration_values(self, force_new_api_key=False):
        """Create/update API key, phone list, and TwiML app on the settings record."""
        self.ensure_one()
        if not self.twilio_account_sid or not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Account SID and Auth Token.")

        service = self.env["twilio.service"]
        client = service.get_client(self.twilio_account_sid, self.twilio_auth_token)
        icp = self.env["ir.config_parameter"].sudo()

        if force_new_api_key or not self.twilio_api_key_sid or not self.twilio_api_secret:
            api_key = service.generate_api_key(client)
            self.twilio_api_key_sid = api_key["api_key_sid"]
            self.twilio_api_secret = api_key["api_secret"]
            icp.set_param(
                "twilio_dialer.api_key_friendly_name",
                api_key.get("api_key_friendly_name", ""),
            )

        self._refresh_incoming_phone_numbers()
        voice_url = service.get_voice_url(self.env)

        try:
            if self.twilio_application_sid:
                twiml_app = service.update_twiml_application(
                    client,
                    self.twilio_application_sid,
                    voice_url,
                    voice_method="GET",
                )
            else:
                twiml_app = service.create_twiml_application(
                    client,
                    voice_url,
                    voice_method="GET",
                )
        except UserError:
            if not self.twilio_application_sid:
                twiml_app = service.create_twiml_application(
                    client,
                    voice_url,
                    voice_method="GET",
                )
            else:
                raise

        self.twilio_application_sid = twiml_app["application_sid"]
        icp.set_param(
            "twilio_dialer.application_friendly_name",
            twiml_app.get("application_friendly_name", ""),
        )
        icp.set_param(
            "twilio_dialer.voice_method",
            twiml_app.get("voice_method", "GET"),
        )
        icp.set_param("twilio_dialer.voice_url", voice_url)
        return True

    def set_values(self):
        self._twilio_preserve_generated_fields()

        if not self.env.context.get("twilio_skip_auto_generate"):
            for record in self:
                if not record._twilio_should_auto_generate():
                    continue
                icp = self.env["ir.config_parameter"].sudo()
                stored_sid = icp.get_param("twilio_dialer.account_sid") or ""
                stored_token = icp.get_param("twilio_dialer.auth_token") or ""
                creds_changed = (
                    record.twilio_account_sid != stored_sid
                    or record.twilio_auth_token != stored_token
                )
                try:
                    record._generate_twilio_configuration_values(
                        force_new_api_key=creds_changed and bool(stored_sid or stored_token)
                    )
                    record._submit_module_registration()
                except UserError as error:
                    _logger.warning("Twilio auto-configuration failed: %s", error)
                    raise UserError(
                        "Could not set up Twilio automatically:\n%s\n\n"
                        "Check your Account SID and Auth Token, then Save again."
                        % error
                    ) from error
                except Exception as error:
                    _logger.exception("Twilio auto-configuration failed")
                    raise UserError(
                        "Could not set up Twilio automatically:\n%s\n\n"
                        "Check your Account SID and Auth Token, then Save again."
                        % error
                    ) from error

        return super().set_values()

    def _submit_module_registration(self):
        """Notify ZantaTech when a Twilio account is connected to the module."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        account_sid = self.twilio_account_sid or icp.get_param("twilio_dialer.account_sid")
        if not account_sid:
            return

        email = (
            (self.twilio_contact_email or "").strip()
            or icp.get_param("twilio_dialer.contact_email")
            or ""
        )
        phone = (
            (self.twilio_contact_phone or "").strip()
            or icp.get_param("twilio_dialer.contact_phone")
            or ""
        )
        payload = {
            "accountSid": account_sid,
            "email": email,
            "phone": phone,
            "message": "New Registration",
            "title": "Odoo Module login",
        }
        try:
            ZantaTechAPI().submit_feedback(payload)
        except ZantaTechAPIError as error:
            _logger.warning("Module registration feedback failed: %s", error)
        except Exception:
            _logger.exception("Unexpected error submitting module registration feedback")

    def _refresh_incoming_phone_numbers(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("twilio_dialer.account_sid", self.twilio_account_sid)
        icp.set_param("twilio_dialer.auth_token", self.twilio_auth_token)

        phone_numbers = self.env["twilio.service"].get_incoming_phone_numbers()
        icp.set_param(
            "twilio_dialer.incoming_phone_numbers",
            json.dumps(phone_numbers),
        )

        available_numbers = {number["phone_number"] for number in phone_numbers}
        if self.twilio_phone_number not in available_numbers:
            self.twilio_phone_number = phone_numbers[0]["phone_number"]

        self.twilio_phone_number = self.env["twilio.service"].validate_phone_number(
            self.twilio_phone_number
        )
        selected_number = next(
            number
            for number in phone_numbers
            if number["phone_number"] == self.twilio_phone_number
        )
        icp.set_param("twilio_dialer.phone_number", self.twilio_phone_number)
        _logger.info(
            "Selected Twilio Incoming Phone Number: %s (SID: %s, Voice URL: %s)",
            selected_number["phone_number"],
            selected_number["sid"],
            selected_number["voice_url"],
        )

    def _get_twilio_settings_action(self):
        """Re-open Twilio Configuration so the form reloads generated fields."""
        action = self.env.ref("twilio_dialer.action_twilio_configuration").sudo().read()[0]
        # Drop transient keys that can break reopening settings after a button click
        context = {
            key: value
            for key, value in dict(self.env.context).items()
            if key not in ("active_id", "active_ids", "active_model", "allowed_company_ids")
            and not key.startswith("default_")
        }
        # .read() returns context as a string — always set a clean dict
        context["module"] = "twilio_dialer"
        action["context"] = context
        return action

    def _reload_twilio_settings(self, title, message, notif_type="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,
                "sticky": False,
                "next": self._get_twilio_settings_action(),
            },
        }

    def execute(self):
        """Save settings; after auto-connect, reload so API key / phones appear."""
        will_auto_connect = False
        if not self.env.context.get("twilio_skip_auto_generate"):
            for record in self:
                record._twilio_preserve_generated_fields()
                if record._twilio_should_auto_generate():
                    will_auto_connect = True
                    break

        result = super().execute()
        if will_auto_connect:
            return self._reload_twilio_settings(
                "Twilio Connection",
                "Connected. API key, application ID, and phone numbers were generated.",
            )
        return result

    def action_refresh_incoming_phone_numbers(self):
        self.ensure_one()

        if not self.twilio_account_sid:
            raise UserError("Please enter your Twilio Account SID.")
        if not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Auth Token.")

        self._refresh_incoming_phone_numbers()
        self.with_context(twilio_skip_auto_generate=True).set_values()

        return self._reload_twilio_settings(
            "Twilio Phone Numbers",
            "Incoming Phone Numbers refreshed successfully.",
        )

    def action_remove_connection(self):
        self.ensure_one()

        account_sid = self.twilio_account_sid
        auth_token = self.twilio_auth_token
        api_key_sid = self.twilio_api_key_sid
        application_sid = self.twilio_application_sid

        if account_sid and auth_token and (api_key_sid or application_sid):
            service = self.env["twilio.service"]
            try:
                client = service.get_client(account_sid, auth_token)
                service.delete_api_key(client, api_key_sid)
                service.delete_twiml_application(client, application_sid)
            except Exception as error:
                _logger.warning("Twilio disconnect cleanup failed: %s", error)

        icp = self.env["ir.config_parameter"].sudo()
        for key in (
            "twilio_dialer.account_sid",
            "twilio_dialer.auth_token",
            "twilio_dialer.contact_email",
            "twilio_dialer.contact_phone",
            "twilio_dialer.phone_number",
            "twilio_dialer.incoming_phone_numbers",
            "twilio_dialer.api_key_sid",
            "twilio_dialer.api_secret",
            "twilio_dialer.api_key_friendly_name",
            "twilio_dialer.application_sid",
            "twilio_dialer.application_friendly_name",
            "twilio_dialer.voice_url",
            "twilio_dialer.voice_method",
        ):
            icp.set_param(key, "")

        self.twilio_account_sid = False
        self.twilio_auth_token = False
        self.twilio_contact_email = False
        self.twilio_contact_phone = False
        self.twilio_phone_number = False
        self.twilio_api_key_sid = False
        self.twilio_api_secret = False
        self.twilio_application_sid = False
        self.with_context(twilio_skip_auto_generate=True).set_values()

        return self._reload_twilio_settings(
            "Twilio Connection",
            "Disconnected. Credentials and generated details were cleared.",
        )

    def action_save_twilio_credentials(self):
        """Save SID/token, generate connection details, then reload the page."""
        self.ensure_one()
        if not self.twilio_account_sid:
            raise UserError("Please enter your Twilio Account SID.")
        if not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Auth Token.")
        if not (self.twilio_contact_email or "").strip():
            raise UserError("Please enter a Contact Email in Account Settings.")

        icp = self.env["ir.config_parameter"].sudo()
        stored_sid = icp.get_param("twilio_dialer.account_sid") or ""
        stored_token = icp.get_param("twilio_dialer.auth_token") or ""
        creds_changed = (
            self.twilio_account_sid != stored_sid
            or self.twilio_auth_token != stored_token
        )
        incomplete = not (
            self.twilio_api_key_sid
            and self.twilio_api_secret
            and self.twilio_application_sid
        )

        try:
            self._generate_twilio_configuration_values(
                force_new_api_key=creds_changed or incomplete
            )
        except UserError as error:
            raise UserError(
                "Could not save Twilio credentials:\n%s\n\n"
                "Check your Account SID and Auth Token, then try again."
                % error
            ) from error

        self.with_context(twilio_skip_auto_generate=True).set_values()
        if creds_changed or incomplete:
            self._submit_module_registration()
        return self._reload_twilio_settings(
            "Twilio Connection",
            "Credentials saved. API key, application ID, and phone numbers are ready.",
        )

    def action_generate_configuration(self):
        """Sync again — recreate API key and reload numbers / TwiML app."""
        self.ensure_one()
        if not self.twilio_account_sid or not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Account SID and Auth Token first.")
        self._generate_twilio_configuration_values(force_new_api_key=True)
        self.with_context(twilio_skip_auto_generate=True).set_values()
        return self._reload_twilio_settings(
            "Twilio Configuration",
            "Synced again. API key, application ID, and phone numbers are up to date.",
        )
