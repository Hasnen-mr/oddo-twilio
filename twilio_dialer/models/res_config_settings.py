# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # UI section toggles (open / close) — stored so the settings view can resolve them
    twilio_section_account_open = fields.Boolean(
        string="Account Details",
        config_parameter="twilio_dialer.section_account_open",
        default=True,
    )
    twilio_section_call_open = fields.Boolean(
        string="Call Settings",
        config_parameter="twilio_dialer.section_call_open",
        default=True,
    )
    twilio_section_ai_open = fields.Boolean(
        string="AI Settings",
        config_parameter="twilio_dialer.section_ai_open",
        default=True,
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
        readonly=True,
        config_parameter="twilio_dialer.voice_url",
    )
    twilio_status = fields.Char(
        string="Status",
        compute="_compute_twilio_status",
        readonly=True,
    )

    # ── Call Settings ─────────────────────────────────────
    twilio_incoming_enabled = fields.Boolean(
        string="Enable Incoming Calls",
        config_parameter="twilio_dialer.incoming_enabled",
        default=True,
    )
    twilio_incoming_record = fields.Boolean(
        string="Record Incoming Calls",
        config_parameter="twilio_dialer.incoming_record",
        default=False,
    )
    twilio_incoming_voicemail = fields.Boolean(
        string="Send Unanswered to Voicemail",
        config_parameter="twilio_dialer.incoming_voicemail",
        default=False,
    )
    twilio_incoming_timeout = fields.Integer(
        string="Incoming Ring Timeout (sec)",
        config_parameter="twilio_dialer.incoming_timeout",
        default=30,
    )
    twilio_outgoing_record = fields.Boolean(
        string="Record Outgoing Calls",
        config_parameter="twilio_dialer.outgoing_record",
        default=False,
    )
    twilio_outgoing_timeout = fields.Integer(
        string="Outgoing Call Timeout (sec)",
        config_parameter="twilio_dialer.outgoing_timeout",
        default=60,
    )
    twilio_outgoing_machine_detection = fields.Boolean(
        string="Answering Machine Detection",
        config_parameter="twilio_dialer.outgoing_machine_detection",
        default=False,
    )
    twilio_outgoing_caller_id_name = fields.Char(
        string="Caller ID Display Name",
        config_parameter="twilio_dialer.outgoing_caller_id_name",
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
            if record.twilio_api_key_sid and record.twilio_application_sid:
                record.twilio_status = "Connected"
            else:
                record.twilio_status = "Not Configured"

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

    def action_refresh_incoming_phone_numbers(self):
        self.ensure_one()

        if not self.twilio_account_sid:
            raise UserError("Please enter your Twilio Account SID.")
        if not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Auth Token.")

        self._refresh_incoming_phone_numbers()
        self.set_values()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Twilio Phone Numbers",
                "message": "Incoming Phone Numbers refreshed successfully.",
                "type": "success",
                "sticky": False,
            },
        }

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
            "twilio_dialer.api_key_sid",
            "twilio_dialer.api_secret",
            "twilio_dialer.api_key_friendly_name",
            "twilio_dialer.application_sid",
            "twilio_dialer.application_friendly_name",
            "twilio_dialer.voice_url",
            "twilio_dialer.voice_method",
        ):
            icp.set_param(key, "")

        self.twilio_api_key_sid = False
        self.twilio_api_secret = False
        self.twilio_application_sid = False
        self.twilio_voice_url = False
        self.set_values()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Twilio Connection",
                "message": "Connection removed. Generated credentials were cleared.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_generate_configuration(self):
        self.ensure_one()

        if not self.twilio_account_sid:
            raise UserError("Please enter your Twilio Account SID.")
        if not self.twilio_auth_token:
            raise UserError("Please enter your Twilio Auth Token.")

        service = self.env["twilio.service"]
        client = service.get_client(self.twilio_account_sid, self.twilio_auth_token)
        api_key = service.generate_api_key(client)
        self.twilio_api_key_sid = api_key["api_key_sid"]
        self.twilio_api_secret = api_key["api_secret"]

        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "twilio_dialer.api_key_friendly_name",
            api_key.get("api_key_friendly_name", ""),
        )
        self._refresh_incoming_phone_numbers()

        try:
            voice_url = service.get_voice_url(self.env)
        except UserError:
            if not self.twilio_application_sid:
                try:
                    twiml_app = service.create_twiml_application(client)
                except UserError:
                    self.set_values()
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": "Twilio Configuration",
                            "message": "API Key and Incoming Phone Numbers were saved, but the TwiML Application could not be created. Verify your Twilio credentials, then try again.",
                            "type": "warning",
                            "sticky": False,
                        },
                    }
                self.twilio_application_sid = twiml_app["application_sid"]
                icp.set_param(
                    "twilio_dialer.application_friendly_name",
                    twiml_app.get("application_friendly_name", ""),
                )
            self.set_values()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Twilio Configuration",
                    "message": "API Key, Incoming Phone Numbers, and TwiML Application were updated. Configure a public HTTPS base URL to enable outbound calls.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        try:
            if self.twilio_application_sid:
                twiml_app = service.update_twiml_application(
                    client,
                    self.twilio_application_sid,
                    voice_url,
                )
            else:
                twiml_app = service.create_twiml_application(client, voice_url)
        except UserError:
            self.set_values()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Twilio Configuration",
                    "message": "API Key and Incoming Phone Numbers were saved, but the TwiML Application could not be configured. Verify the public HTTPS URL and Twilio credentials, then try again.",
                    "type": "warning",
                    "sticky": False,
                },
            }
        self.twilio_application_sid = twiml_app["application_sid"]
        self.twilio_voice_url = voice_url
        icp.set_param(
            "twilio_dialer.application_friendly_name",
            twiml_app.get("application_friendly_name", ""),
        )
        icp.set_param(
            "twilio_dialer.voice_method",
            twiml_app.get("voice_method", "POST"),
        )
        icp.set_param("twilio_dialer.voice_url", voice_url)

        self.set_values()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Twilio Configuration",
                "message": "Configuration generated successfully.",
                "type": "success",
                "sticky": False,
            },
        }
