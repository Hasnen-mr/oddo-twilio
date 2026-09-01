# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.release import version as odoo_release_version
from twilio.base.exceptions import TwilioRestException
from .twilio_service import sanitize_secret_message
from ..services import MyBroadcastAPI, MyBroadcastAPIError, ZantaTechAPI, ZantaTechAPIError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Complete MCP Settings compatibility fields for inherited views
    mcp_enabled = fields.Boolean(string="Enable MCP Server", config_parameter="mcp_server.enabled", default=False)
    mcp_enable_oauth = fields.Boolean(string="Enable OAuth", config_parameter="mcp_server.enable_oauth", default=False)
    mcp_request_limit = fields.Integer(string="Request Limit", config_parameter="mcp_server.request_limit", default=100)
    mcp_enable_logging = fields.Boolean(string="Enable Logging", config_parameter="mcp_server.enable_logging", default=False)
    mcp_enable_rate_limiting = fields.Boolean(string="Enable Rate Limiting", config_parameter="mcp_server.enable_rate_limiting", default=False)
    mcp_log_retention_days = fields.Integer(string="Log Retention Days", config_parameter="mcp_server.log_retention_days", default=30)
    mcp_default_limit = fields.Integer(string="Default Limit", config_parameter="mcp_server.default_limit", default=80)
    mcp_max_limit = fields.Integer(string="Max Limit", config_parameter="mcp_server.max_limit", default=1000)
    mcp_max_smart_fields = fields.Integer(string="Max Smart Fields", config_parameter="mcp_server.max_smart_fields", default=10)
    mcp_max_related_items = fields.Integer(string="Max Related Items", config_parameter="mcp_server.max_related_items", default=5)
    mcp_allowed_origins = fields.Char(string="Allowed Origins", config_parameter="mcp_server.allowed_origins")
    mcp_port = fields.Integer(string="MCP Port", config_parameter="mcp.port", default=8000)
    mcp_host = fields.Char(string="MCP Host", config_parameter="mcp.host", default="127.0.0.1")
    mcp_log_level = fields.Selection([("info", "Info"), ("debug", "Debug"), ("warning", "Warning"), ("error", "Error")], string="Log Level", config_parameter="mcp.log_level", default="info")
    mcp_api_key = fields.Char(string="API Key", config_parameter="mcp.api_key")

    # Left-sidebar section on Configuration page (client-only, not persisted)
    twilio_config_section = fields.Selection(
        selection=[
            ("account", "Account Settings"),
            ("call", "Call Settings"),
            ("allocation", "My Team"),
            ("ai", "AI Settings"),
            ("billing", "Billing"),
        ],
        string="Configuration Section",
        default="account",
    )
    twilio_allocation_panel = fields.Char(
        string="Allocation Panel",
        default="1",
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
    twilio_incoming_welcome_greeting = fields.Boolean(
        string="Welcome Greeting",
    )
    twilio_incoming_welcome_greeting_text = fields.Text(
        string="Greeting Message Text",
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
    twilio_incoming_transcription = fields.Boolean(
        string="Enable Incoming Transcription",
        config_parameter="twilio_dialer.incoming_transcription",
        default=False,
    )
    twilio_outgoing_transcription = fields.Boolean(
        string="Enable Outgoing Transcription",
        config_parameter="twilio_dialer.outgoing_transcription",
        default=False,
    )
    twilio_call_settings_error = fields.Char(readonly=True)
    twilio_call_settings_autosave = fields.Char(
        string="Call Settings Autosave",
        default="1",
    )
    twilio_ai_settings_link = fields.Char(
        string="AI Settings Link",
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
    twilio_openai_speech_model = fields.Selection(
        selection=[
            ("whisper-1", "Whisper v1 (whisper-1)"),
            ("gpt-4o-mini-transcribe", "GPT-4o Mini Transcribe (gpt-4o-mini-transcribe)"),
        ],
        string="OpenAI Speech Model",
        config_parameter="twilio_dialer.openai_speech_model",
        default="whisper-1",
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
    twilio_ai_api_key_issue = fields.Boolean(
        string="AI API Key Issue",
        compute="_compute_twilio_ai_api_key_issue",
    )

    @api.depends(
        "twilio_ai_provider",
        "twilio_openai_api_key",
        "twilio_anthropic_api_key",
        "twilio_gemini_api_key",
        "twilio_deepgram_api_key",
    )
    def _compute_twilio_ai_api_key_issue(self):
        icp = self.env["ir.config_parameter"].sudo()
        param_map = {
            "openai": "twilio_dialer.openai_api_key",
            "anthropic": "twilio_dialer.anthropic_api_key",
            "gemini": "twilio_dialer.gemini_api_key",
            "deepgram": "twilio_dialer.deepgram_api_key",
        }
        for record in self:
            provider = record.twilio_ai_provider or icp.get_param(
                "twilio_dialer.ai_provider", "openai"
            ) or "openai"
            field_map = {
                "openai": record.twilio_openai_api_key,
                "anthropic": record.twilio_anthropic_api_key,
                "gemini": record.twilio_gemini_api_key,
                "deepgram": record.twilio_deepgram_api_key,
            }
            # Password fields often round-trip empty; fall back to stored config.
            api_key = (field_map.get(provider) or "").strip()
            if not api_key:
                api_key = (icp.get_param(param_map.get(provider, ""), "") or "").strip()
            record.twilio_ai_api_key_issue = not self._is_plausible_ai_api_key(
                provider, api_key
            )

    @staticmethod
    def _is_plausible_ai_api_key(provider, api_key):
        """Lightweight local check — empty or obviously bad keys are flagged."""
        if not api_key:
            return False
        if len(api_key) < 12:
            return False
        if provider == "openai":
            return api_key.startswith("sk-")
        if provider == "anthropic":
            return api_key.startswith("sk-ant-")
        return True

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

        _logger.info("Raw API response:\n%s", json.dumps(payload, indent=3, default=str))

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
        _logger.info("Parsed incoming:\n%s", json.dumps(incoming, indent=3, default=str))
        _logger.info("Parsed outgoing:\n%s", json.dumps(outgoing, indent=3, default=str))
        return incoming, outgoing, False

    @staticmethod
    def _call_settings_values(incoming, outgoing):
        """Map validated API sections to transient fields only."""
        values = {
            "twilio_incoming_enabled": incoming.get("allow"),
            "twilio_incoming_record": incoming.get("record"),
            "twilio_incoming_voicemail": incoming.get("voicemail"),
            "twilio_incoming_voicemail_text": incoming.get("voicemailText", ""),
            "twilio_incoming_welcome_greeting": incoming.get("welcomeGreeting", incoming.get("welcome")),
            "twilio_incoming_welcome_greeting_text": incoming.get(
                "welcomeGreetingText",
                incoming.get("welcomeText", ""),
            ),
            "twilio_incoming_forward": incoming.get("forward"),
            "twilio_incoming_forward_to": incoming.get("forwardTo", ""),
            "twilio_outgoing_record": outgoing.get("record"),
            "twilio_outgoing_smart_copy": outgoing.get("smartCopy"),
        }
        if incoming.get("transcription") is not None:
            values["twilio_incoming_transcription"] = incoming["transcription"]
        if outgoing.get("transcription") is not None:
            values["twilio_outgoing_transcription"] = outgoing["transcription"]
        return values

    @api.model
    def _twilio_is_configured(self):
        icp = self.env["ir.config_parameter"].sudo()
        return bool(
            icp.get_param("twilio_dialer.api_key_sid")
            and icp.get_param("twilio_dialer.application_sid")
        )

    @api.model
    def action_open_twilio_configuration(self, *args, **kwargs):
        """Open Twilio configuration directly into Twilio Call Auto Dialer app settings."""
        return {
            "type": "ir.actions.act_window",
            "name": "Settings",
            "res_model": "res.config.settings",
            "view_mode": "form",
            "target": "inline",
            "context": {"module": "twilio_dialer", "bin_size": False},
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

        voicemail = bool(values.get("twilio_incoming_voicemail"))
        voicemail_text = values.get("twilio_incoming_voicemail_text") or ""
        welcome_greeting = bool(values.get("twilio_incoming_welcome_greeting"))
        welcome_greeting_text = values.get("twilio_incoming_welcome_greeting_text") or ""
        forward = bool(values.get("twilio_incoming_forward"))
        forward_to = values.get("twilio_incoming_forward_to") or ""

        if voicemail and forward:
            _logger.warning(
                "Both voicemail and forward enabled — normalizing to voicemail only."
            )
            forward = False
            forward_to = ""

        incoming_transcription = bool(values.get("twilio_incoming_transcription"))
        outgoing_transcription = bool(values.get("twilio_outgoing_transcription"))

        icp = self.env["ir.config_parameter"].sudo()
        # Persist local copies for webhook fallback / greeting playback
        icp.set_param("twilio_dialer.incoming_transcription", incoming_transcription)
        icp.set_param("twilio_dialer.outgoing_transcription", outgoing_transcription)
        icp.set_param("twilio_dialer.incoming_welcome_greeting", welcome_greeting)
        icp.set_param(
            "twilio_dialer.incoming_welcome_greeting_text",
            welcome_greeting_text,
        )

        # Ensure AI transcript flag is enabled automatically when any UI transcription
        # option is turned on. Do not automatically disable AI transcripts when the
        # UI toggles are turned off to preserve backwards compatibility with any
        # explicit admin setting for ai_enable_transcript.
        try:
            if incoming_transcription or outgoing_transcription:
                _logger.info(
                    "autosave_call_settings: attempting to set twilio_dialer.ai_enable_transcript=True (incoming=%s outgoing=%s)",
                    incoming_transcription,
                    outgoing_transcription,
                )
                icp.set_param("twilio_dialer.ai_enable_transcript", "True")
                # Immediately read back and log the persisted value for diagnostics
                try:
                    persisted = icp.get_param("twilio_dialer.ai_enable_transcript")
                except Exception as e:
                    _logger.exception(
                        "autosave_call_settings: error reading back twilio_dialer.ai_enable_transcript after set: %s",
                        e,
                    )
                    raise
                _logger.info(
                    "autosave_call_settings: twilio_dialer.ai_enable_transcript persisted value=%r",
                    persisted,
                )

                # Also update the transient res.config.settings record for the current
                # user so that any subsequent set_values() (which persists transient
                # fields to ir.config_parameter) will not overwrite this parameter back
                # to False. This keeps the autosave and the main save flow in sync.
                try:
                    settings_model = self.env["res.config.settings"].sudo()
                    recent = settings_model.search(
                        [("create_uid", "=", self.env.uid)],
                        order="create_date desc",
                        limit=1,
                    )
                    if recent:
                        _logger.info(
                            "autosave_call_settings: updating transient res.config.settings id=%s twilio_ai_enable_transcript=True",
                            recent.id,
                        )
                        # write the transient field so super().set_values() will persist True
                        recent.write({"twilio_ai_enable_transcript": True})
                    else:
                        _logger.info(
                            "autosave_call_settings: no transient res.config.settings record found to update"
                        )
                except Exception:
                    _logger.exception(
                        "autosave_call_settings: failed to update transient res.config.settings record"
                    )
        except Exception:
            # Let exceptions bubble up after logging — caller handles errors; do not
            # suppress to comply with project rules.
            _logger.exception("Failed to set twilio_dialer.ai_enable_transcript config parameter")
            raise

        if values.get("twilio_incoming_enabled"):
            try:
                # Assign stored TwiML Application SID to every Twilio phone number.
                self.env["twilio.service"].configure_incoming_phone_number(
                    phone_number=phone_number
                )
            except Exception as error:
                _logger.warning(
                    "Failed to assign TwiML Application to Twilio phone numbers: %s",
                    error,
                )

        settings = {
            "incomingCallSetting": {
                "allow": bool(values.get("twilio_incoming_enabled")),
                "record": bool(values.get("twilio_incoming_record")),
                "transcription": incoming_transcription,
                "voicemail": voicemail,
                "voicemailText": voicemail_text,
                "welcomeGreeting": welcome_greeting,
                "welcomeGreetingText": welcome_greeting_text,
                "forward": forward,
                "forwardTo": forward_to,
            },
            "outgoingCallSetting": {
                "record": bool(values.get("twilio_outgoing_record")),
                "transcription": outgoing_transcription,
                "smartCopy": bool(values.get("twilio_outgoing_smart_copy")),
            },
        }
        _logger.info(
            "Sending call-settings payload:\n%s",
            json.dumps(settings, indent=3),
        )
        try:
            payload = MyBroadcastAPI().save_call_settings(account_sid, settings)
        except MyBroadcastAPIError as error:
            return {"success": False, "message": str(error)}

        _logger.info(
            "Saving incoming transcription=%s outgoing transcription=%s",
            settings["incomingCallSetting"]["transcription"],
            settings["outgoingCallSetting"]["transcription"],
        )

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

    def validate_contact_email(self):
        """Validate contact email field before any external API calls or registration.

        Raises UserError if email is missing or improperly formatted.
        """
        import re
        self.ensure_one()
        email = (self.twilio_contact_email or "").strip()
        if not email:
            raise UserError("Email is required.")
        regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(regex, email):
            raise UserError("Please enter a valid email address.")
        return email

    def _generate_twilio_configuration_values(self, force_new_api_key=False):
        """Create/update API key, phone list, and TwiML app on the settings record."""
        self.ensure_one()
        self.validate_contact_email()
        if not self.twilio_account_sid or not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Account SID and Auth Token.")

        service = self.env["twilio.service"]
        client = service.get_client(self.twilio_account_sid, self.twilio_auth_token)
        icp = self.env["ir.config_parameter"].sudo()

        # Recreate API key when missing, forced, or deleted in Twilio (causes AccessTokenInvalid 20101).
        need_new_api_key = force_new_api_key or not self.twilio_api_key_sid or not self.twilio_api_secret
        if not need_new_api_key and self.twilio_api_key_sid:
            try:
                client.keys(self.twilio_api_key_sid).fetch()
            except TwilioRestException as err:
                if err.status == 404:
                    _logger.warning(
                        "Stored Twilio API Key %s not found; regenerating.",
                        self.twilio_api_key_sid,
                    )
                    need_new_api_key = True
                else:
                    raise UserError(
                        "Unable to verify Twilio API Key:\n%s" % err
                    ) from err

        if need_new_api_key:
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
        except UserError as error:
            # Stale Application SID (deleted in Twilio console) → create a new one.
            err_text = str(error).lower()
            if self.twilio_application_sid and (
                "20404" in err_text or "not found" in err_text or "404" in err_text
            ):
                _logger.warning(
                    "Stored TwiML Application %s not found; recreating.",
                    self.twilio_application_sid,
                )
                twiml_app = service.create_twiml_application(
                    client,
                    voice_url,
                    voice_method="GET",
                )
            elif not self.twilio_application_sid:
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
        _logger.info(
            "set_values() START — twilio_incoming_transcription=%s twilio_outgoing_transcription=%s",
            self.twilio_incoming_transcription,
            self.twilio_outgoing_transcription,
        )
        _logger.info("set_values() — record state: %s", {
            'id': self.id if hasattr(self, 'id') else 'N/A',
            'twilio_incoming_transcription': self.twilio_incoming_transcription,
            'twilio_outgoing_transcription': self.twilio_outgoing_transcription,
        })
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
                    clean_err = sanitize_secret_message(error, [record.twilio_auth_token, record.twilio_account_sid, record.twilio_api_secret])
                    raise UserError(
                        "Could not set up Twilio automatically:\n%s\n\n"
                        "Check your Account SID and Auth Token, then Save again."
                        % clean_err
                    ) from error
                except Exception as error:
                    _logger.exception("Twilio auto-configuration failed")
                    clean_err = sanitize_secret_message(error, [record.twilio_auth_token, record.twilio_account_sid, record.twilio_api_secret])
                    raise UserError(
                        "Could not set up Twilio automatically:\n%s\n\n"
                        "Check your Account SID and Auth Token, then Save again."
                        % clean_err
                    ) from error

        result = super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("twilio_dialer.incoming_transcription", self.twilio_incoming_transcription)
        icp.set_param("twilio_dialer.outgoing_transcription", self.twilio_outgoing_transcription)
        _logger.info(
            "set_values() after super() — ir.config_parameter incoming_transcription=%s outgoing_transcription=%s",
            icp.get_param("twilio_dialer.incoming_transcription"),
            icp.get_param("twilio_dialer.outgoing_transcription"),
        )
        return result

    def write(self, vals):
        """Log write() calls to trace when and how settings are saved."""
        _logger.info("write() CALLED with vals keys: %s", list(vals.keys()) if vals else [])
        _logger.info("write() — transcription in vals: incoming=%s, outgoing=%s", 
                     vals.get('twilio_incoming_transcription'), 
                     vals.get('twilio_outgoing_transcription'))
        _logger.info("write() — calling super().write()")
        result = super().write(vals)
        _logger.info("write() — after super().write(), result=%s", result)
        
        # CRITICAL FIX: For TransientModel, web_save doesn't call set_values() automatically
        # We must explicitly call set_values() after write() to persist config_parameter fields
        
        return result

    def create(self, vals_list):
        """Log create() calls to trace record creation."""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        _logger.info("create() CALLED with %d record(s)", len(vals_list))
        for i, vals in enumerate(vals_list):
            _logger.info("create() [%d] — vals keys: %s", i, list(vals.keys()) if vals else [])
            _logger.info("create() [%d] — transcription in vals: incoming=%s, outgoing=%s", 
                         i, vals.get('twilio_incoming_transcription'), vals.get('twilio_outgoing_transcription'))
        result = super().create(vals_list)
        return result

    def action_open_credentials_help(self):
        """Open the Twilio credentials finder guide."""
                # Broadcast disconnection to all active web clients to reset dialer & device states
        try:
            channels = [(p, "twilio_connection_disconnected", {}) for p in self.env["res.partner"].sudo().search([])]
            self.env["bus.bus"]._sendmany(channels)
        except Exception:
            pass

        return {
            "type": "ir.actions.client",
            "tag": "twilio_dialer.action_credentials_help",
            "target": "new",
        }

    def _get_formatted_odoo_base_version(self, odoo_version=None):
        """Format Odoo version dynamically as:
        Normal (Community): 18.0.DD.MM (e.g. 18.0.26.08)
        Pro (Enterprise): 18.0.DD.MM-pro (e.g. 18.0.26.08-pro)
        """
        raw_version = (odoo_version or "").strip() or odoo_release_version or "18.0"

        # Detect Enterprise / Pro
        is_enterprise = False
        if "+e" in raw_version.lower() or "-pro" in raw_version.lower() or "-e" in raw_version.lower():
            is_enterprise = True
        else:
            try:
                import odoo.release as odoo_release
                if hasattr(odoo_release, "version_info") and len(odoo_release.version_info) > 5 and odoo_release.version_info[5] == "e":
                    is_enterprise = True
            except Exception:
                pass
            if not is_enterprise:
                try:
                    if self.env["ir.module.module"].sudo().search([("name", "=", "web_enterprise"), ("state", "=", "installed")], limit=1):
                        is_enterprise = True
                except Exception:
                    pass

        # Extract major series (e.g. 18.0)
        series_match = re.search(r"(\d+\.\d+)", raw_version)
        series = series_match.group(1) if series_match else "18.0"

        # Extract date (DD and MM)
        # Matches YYYYMMDD (e.g. 20260826 -> MM=08, DD=26)
        date_match = re.search(r"\b\d{4}(\d{2})(\d{2})\b", raw_version)
        if date_match:
            mm = date_match.group(1)
            dd = date_match.group(2)
        else:
            # Matches DD.MM or MM.DD or DDMM
            dots_match = re.search(r"\b(\d{2})\.(\d{2})\b", raw_version)
            if dots_match:
                dd, mm = dots_match.group(1), dots_match.group(2)
            else:
                from datetime import date
                dd = date.today().strftime("%d")
                mm = date.today().strftime("%m")

        if is_enterprise:
            return f"{series}.{dd}.{mm}-pro"
        return f"{series}.{dd}.{mm}"

    def _get_twilio_dialer_installed_version(self):
        """Get Twilio Dialer module version string."""
        try:
            mod = self.env["ir.module.module"].sudo().search([("name", "=", "twilio_dialer")], limit=1)
            if mod:
                v = (mod.latest_version or mod.installed_version or "").strip()
                if v:
                    return v
        except Exception:
            pass
        try:
            import odoo.modules.manifest as manifest_util
            mf = manifest_util.get_manifest("twilio_dialer")
            if mf and mf.get("version"):
                return str(mf.get("version")).strip()
        except Exception:
            pass
        return "18.0.26.08"

    def _submit_module_registration(self, odoo_version=None):
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

        formatted_odoo_version = self._get_formatted_odoo_base_version(odoo_version)
        title = "Odoo Module login"
        if formatted_odoo_version:
            title = "%s %s" % (title, formatted_odoo_version)

        payload = {
            "accountSid": account_sid,
            "email": email,
            "phone": phone,
            "message": "New Registration",
            "title": title,
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
        try:
            self.env["twilio.service"].configure_incoming_phone_number()
        except Exception as err:
            _logger.warning("Auto-configuring all incoming numbers failed: %s", err)
        _logger.info(
            "Selected Twilio Incoming Phone Number: %s (SID: %s, Voice URL: %s)",
            selected_number["phone_number"],
            selected_number["sid"],
            selected_number["voice_url"],
        )

    def _get_twilio_settings_action(self):
        """Re-open Twilio Configuration so the form reloads generated fields."""
        return self.action_open_twilio_configuration()

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
        _logger.info("execute() CALLED — twilio_incoming_transcription=%s twilio_outgoing_transcription=%s", 
                     self.twilio_incoming_transcription, self.twilio_outgoing_transcription)
        will_auto_connect = False
        if not self.env.context.get("twilio_skip_auto_generate"):
            for record in self:
                record._twilio_preserve_generated_fields()
                if record._twilio_should_auto_generate():
                    will_auto_connect = True
                    break

        _logger.info("execute() — calling super().execute()")
        result = super().execute()
        _logger.info("execute() — after super().execute(), result=%s", result)
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
        """Disconnect Twilio and clear all stored credentials.

        Reads SIDs from config parameters first so cleanup still works even if
        the settings form save wiped transient field values.
        """
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()

        account_sid = self.twilio_account_sid or icp.get_param("twilio_dialer.account_sid")
        auth_token = self.twilio_auth_token or icp.get_param("twilio_dialer.auth_token")
        api_key_sid = self.twilio_api_key_sid or icp.get_param("twilio_dialer.api_key_sid")
        application_sid = (
            self.twilio_application_sid or icp.get_param("twilio_dialer.application_sid")
        )

        if account_sid and auth_token and (api_key_sid or application_sid):
            service = self.env["twilio.service"]
            try:
                client = service.get_client(account_sid, auth_token)
                service.delete_api_key(client, api_key_sid)
                service.delete_twiml_application(client, application_sid)
            except Exception as error:
                _logger.warning("Twilio disconnect cleanup failed: %s", error)

        # Purge cached numbers and allocations from database
        self.env["twilio.phone.number"].sudo().search([("phone_number", "!=", "ALL")]).unlink()
        self.env["twilio.number.allocation"].sudo().search([]).unlink()

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
            "twilio_dialer.incoming_transcription",
            "twilio_dialer.outgoing_transcription",
        ):
            icp.set_param(key, "")

        vals = {
            "twilio_account_sid": False,
            "twilio_auth_token": False,
            "twilio_contact_email": False,
            "twilio_contact_phone": False,
            "twilio_phone_number": False,
            "twilio_api_key_sid": False,
            "twilio_api_secret": False,
            "twilio_application_sid": False,
            "twilio_incoming_transcription": False,
            "twilio_outgoing_transcription": False,
            "twilio_config_section": "account",
        }
        self.with_context(twilio_skip_auto_generate=True).write(vals)
        self.with_context(twilio_skip_auto_generate=True).set_values()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Twilio Connection",
                "message": "Disconnected. Credentials and generated details were cleared.",
                "type": "success",
                "sticky": False,
                "next": self.env["res.config.settings"].with_context(
                    module="twilio_dialer",
                    default_twilio_config_section="account",
                ).action_open_twilio_configuration(),
            },
        }

    def action_save_twilio_credentials(self):
        """Save SID/token, generate connection details, then reload the page."""
        self.ensure_one()
        self.validate_contact_email()
        if not self.twilio_account_sid:
            raise UserError("Please enter your Twilio Account SID.")
        if not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Auth Token.")

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
            clean_err = sanitize_secret_message(error, [self.twilio_auth_token, self.twilio_account_sid, self.twilio_api_secret])
            raise UserError(
                "Could not save Twilio credentials:\n%s\n\n"
                "Check your Account SID and Auth Token, then try again."
                % clean_err
            ) from error
        except Exception as error:
            clean_err = sanitize_secret_message(error, [self.twilio_auth_token, self.twilio_account_sid, self.twilio_api_secret])
            raise UserError(
                "Could not save Twilio credentials:\n%s\n\n"
                "Check your Account SID and Auth Token, then try again."
                % clean_err
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

    @api.model
    def twilio_wizard_connect(
        self,
        account_sid="",
        auth_token="",
        email="",
        phone="",
        odoo_version="",
        allow_incoming=True,
    ):
        """Connect Twilio from the dashboard onboarding wizard.

        Saves credentials, generates API key / TwiML app / phone numbers,
        submits registration feedback (email, phone, Odoo version), and
        returns a JSON-friendly result for the OWL wizard.
        """
        account_sid = (account_sid or "").strip()
        auth_token = (auth_token or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        odoo_version = (odoo_version or "").strip()

        if not account_sid:
            return {"success": False, "error": "Please enter your Twilio Account SID."}
        if not auth_token:
            return {"success": False, "error": "Please enter your Twilio Auth Token."}
        if not email:
            return {"success": False, "error": "Email is required."}

        settings = self.create(
            {
                "twilio_account_sid": account_sid,
                "twilio_auth_token": auth_token,
                "twilio_contact_email": email,
                "twilio_contact_phone": phone or False,
                "twilio_incoming_enabled": bool(allow_incoming),
            }
        )
        try:
            settings.validate_contact_email()
            settings._generate_twilio_configuration_values(force_new_api_key=True)
            settings.with_context(twilio_skip_auto_generate=True).set_values()
            settings._submit_module_registration(odoo_version=odoo_version)
        except UserError as error:
            clean_err = sanitize_secret_message(error, [auth_token, account_sid])
            return {"success": False, "error": clean_err}
        except Exception as error:
            _logger.exception("Twilio wizard connect failed")
            clean_err = sanitize_secret_message(error, [auth_token, account_sid])
            return {
                "success": False,
                "error": "Could not connect Twilio: %s" % clean_err,
            }

        return {
            "success": True,
            "phone_number": settings.twilio_phone_number or "",
        }

    @api.model
    def twilio_send_registration_otp(self, email="", account_sid="", first_name=""):
        """Send 6-digit OTP verification email for registration."""
        email = (email or "").strip()
        account_sid = (account_sid or "").strip()
        first_name = (first_name or "").strip() or (self.env.user.name or "User").split()[0]

        if not email:
            return {"success": False, "error": "Please enter a valid email address."}
        if not account_sid:
            return {"success": False, "error": "Twilio Account SID is required."}

        try:
            api_client = MyBroadcastAPI()
            res = api_client.send_otp(
                email=email,
                account_sid=account_sid,
                first_name=first_name,
                purpose="registration",
            )
            return {
                "success": True,
                "message": res.get("message") or "Verification code sent to your email.",
                "expiresInSeconds": res.get("expiresInSeconds", 600),
            }
        except MyBroadcastAPIError as e:
            err_msg = str(e)
            if "limit reached" in err_msg.lower():
                err_msg = "Daily email limit reached (5 per email per day). You can use a code already sent to your inbox (active for 10 minutes), or try again tomorrow."
            return {"success": False, "error": err_msg}
        except Exception as e:
            _logger.exception("Failed to send registration OTP")
            return {
                "success": False,
                "error": "Failed to send verification email. Please check your network and try again.",
            }

    @api.model
    def twilio_verify_registration_otp(self, email="", account_sid="", otp="", allow_incoming=None):
        """Verify 6-digit OTP code submitted by user."""
        email = (email or "").strip()
        account_sid = (account_sid or "").strip()
        otp = (otp or "").strip()

        if not email:
            return {"success": False, "error": "Email address is required."}
        if not account_sid:
            return {"success": False, "error": "Twilio Account SID is required."}
        if not otp:
            return {"success": False, "error": "Please enter the 6-digit verification code."}

        try:
            api_client = MyBroadcastAPI()
            res = api_client.verify_otp(email=email, account_sid=account_sid, otp=otp)
            verified = bool(res.get("verified", True))
            if verified and allow_incoming is not None:
                # Update call settings incoming switch
                try:
                    enabled_str = "True" if allow_incoming else "False"
                    icp = self.env["ir.config_parameter"].sudo()
                    icp.set_param("twilio_dialer.incoming_enabled", enabled_str)
                    icp.set_param("twilio_dialer.twilio_incoming_enabled", enabled_str)
                    if allow_incoming:
                        self.env["twilio.service"].configure_incoming_phone_number()
                    api_client.save_call_settings(
                        account_sid,
                        {"incomingCallSetting": {"allow": bool(allow_incoming)}},
                    )
                except Exception as ex:
                    _logger.warning("Failed to save incoming call setting on OTP verify: %s", ex)

            return {
                "success": True,
                "verified": verified,
                "message": res.get("message") or "Email verified successfully.",
            }
        except MyBroadcastAPIError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            _logger.exception("Failed to verify registration OTP")
            return {
                "success": False,
                "error": "Failed to verify code. Please check the code and try again.",
            }

    @api.model
    def twilio_update_incoming_setting(self, allow_incoming=True):
        """Sync incoming call setting and configure Twilio Application ID on phone numbers."""
        icp = self.env["ir.config_parameter"].sudo()
        enabled_str = "True" if allow_incoming else "False"
        icp.set_param("twilio_dialer.incoming_enabled", enabled_str)
        icp.set_param("twilio_dialer.twilio_incoming_enabled", enabled_str)
        account_sid = icp.get_param("twilio_dialer.account_sid")

        if allow_incoming:
            try:
                self.env["twilio.service"].configure_incoming_phone_number()
            except Exception as e:
                _logger.warning("Failed to configure incoming phone number on toggle change: %s", e)

        if account_sid:
            try:
                MyBroadcastAPI().save_call_settings(
                    account_sid,
                    {"incomingCallSetting": {"allow": bool(allow_incoming)}},
                )
            except Exception as e:
                _logger.warning("Failed to save incoming call settings on toggle change: %s", e)

        return {"success": True, "incoming_enabled": bool(allow_incoming)}

    @api.model
    def twilio_update_contact_email(self, email=""):
        """Update stored contact email when user fixes a typo."""
        email = (email or "").strip()
        if email:
            self.env["ir.config_parameter"].sudo().set_param(
                "twilio_dialer.contact_email", email
            )
        return {"success": True, "email": email}

    @api.model
    def twilio_get_call_settings_api(self, account_sid=""):
        """Fetch call settings from MyBroadcast /get-call-settings endpoint.
        Called on-demand by client when 10-minute client cache expires.
        """
        icp = self.env["ir.config_parameter"].sudo()
        account_sid = (account_sid or "").strip() or (icp.get_param("twilio_dialer.account_sid") or "").strip()
        if not account_sid:
            return {"success": False, "error": "Account SID is required."}

        try:
            from ..services import MyBroadcastAPI
            api_client = MyBroadcastAPI()
            payload = api_client.get_call_settings(account_sid)
            incoming, outgoing, error = self._parse_call_settings(payload)
            if not error:
                call_values = self._call_settings_values(incoming, outgoing)
                # Cache parsed values in ICP for offline / fast fallback
                for k, v in call_values.items():
                    if k.startswith("twilio_"):
                        param_name = k.replace("twilio_", "twilio_dialer.")
                        icp.set_param(param_name, str(v) if v is not None else "")
                if "twilio_incoming_enabled" in call_values:
                    icp.set_param(
                        "twilio_dialer.incoming_enabled",
                        "True" if call_values["twilio_incoming_enabled"] else "False",
                    )
            return {
                "success": True,
                "data": payload,
            }
        except Exception as e:
            _logger.warning("twilio_get_call_settings_api error: %s", e)
            return {
                "success": False,
                "error": str(e),
            }




