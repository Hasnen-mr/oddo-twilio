import logging
import re

from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class TwilioService(models.AbstractModel):
    _name = "twilio.service"
    _description = "Twilio Service"

    _default_api_key_friendly_name = "Odoo Power Dialer"
    _default_application_friendly_name = "Odoo Power Dialer"
    _default_voice_method = "GET"
    # Hosted Smart Tools webhook (Chrome extension / shared call-setup).
    # Twilio calls this URL for outbound dial instructions — no public Odoo URL required.
    _default_voice_url = "https://extension.mybroadcast.online/call-setup"

    def get_client(self, account_sid, auth_token):
        try:
            return Client(account_sid, auth_token)
        except Exception as e:
            raise UserError(f"Failed to initialize Twilio client:\n{str(e)}")

    def validate_phone_number(self, phone_number):
        normalized = (phone_number or "").strip()
        if not normalized:
            raise UserError("Please enter your Twilio Phone Number.")
        if not normalized.startswith("+"):
            raise UserError("Twilio Phone Number must start with '+'.")
        if not re.fullmatch(r"\+\d{8,15}", normalized):
            raise UserError(
                "Twilio Phone Number must be in E.164 format, for example +15551234567."
            )
        return normalized

    def get_twilio_phone_number(self):
        ICP = self.env["ir.config_parameter"].sudo()
        phone_number = ICP.get_param("twilio_dialer.phone_number")
        return self.validate_phone_number(phone_number)

    def get_verified_twilio_phone_number(self):
        phone_number = self.get_twilio_phone_number()
        incoming_numbers = self.get_incoming_phone_numbers()

        if phone_number not in {
            incoming_number["phone_number"] for incoming_number in incoming_numbers
        }:
            raise UserError(
                "The configured Twilio Phone Number is not an Incoming Phone Number "
                "for the configured Twilio account. Select a valid number and try again."
            )

        return phone_number

    def get_incoming_phone_numbers(self, env=None):
        env = env or self.env
        ICP = env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")

        if not account_sid or not auth_token:
            raise UserError("Please configure your Twilio Account SID and Auth Token.")

        try:
            client = self.get_client(account_sid, auth_token)
            phone_numbers = [
                {
                    "sid": number.sid,
                    "phone_number": number.phone_number,
                    "friendly_name": number.friendly_name,
                    "voice_url": number.voice_url,
                }
                for number in client.incoming_phone_numbers.stream()
            ]
        except TwilioRestException as e:
            if e.status in (401, 403):
                raise UserError("Twilio credentials are invalid.")
            raise UserError(f"Twilio API error while retrieving phone numbers: {str(e)}")
        except UserError:
            raise
        except Exception as e:
            _logger.error("Failed to retrieve Twilio incoming phone numbers: %s", str(e))
            raise UserError("Unable to connect to Twilio to retrieve phone numbers.")

        if not phone_numbers:
            raise UserError("No Twilio Incoming Phone Numbers are configured for this account.")

        _logger.info("Found %s Twilio Incoming Phone Numbers.", len(phone_numbers))
        return phone_numbers

    def get_voice_url(self, env=None):
        """Return the Smart Tools Voice URL used by the TwiML Application.

        Uses the hosted extension call-setup endpoint by default so Odoo does
        not need a public URL. An explicit non-Odoo override in ICP is kept.
        """
        ICP = (env or self.env)["ir.config_parameter"].sudo()
        stored = (ICP.get_param("twilio_dialer.voice_url") or "").strip()
        # Ignore old local/Odoo-built URLs from earlier versions
        if stored and "/twilio_dialer/call_setup" not in stored:
            return stored
        return self._default_voice_url

    def generate_api_key(self, client, friendly_name=None):
        try:
            api_key = client.new_keys.create(
                friendly_name=friendly_name or self._default_api_key_friendly_name
            )
            return {
                "api_key_sid": api_key.sid,
                "api_secret": api_key.secret,
                "api_key_friendly_name": friendly_name or self._default_api_key_friendly_name,
            }
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Failed to generate Twilio API Key:\n{str(e)}")

    def create_twiml_application(self, client, voice_url=None, voice_method=None, friendly_name=None):
        request_url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{client.username}/Applications.json"
        )
        voice_url = voice_url or self._default_voice_url
        voice_method = voice_method or self._default_voice_method
        payload = {
            "friendly_name": friendly_name or self._default_application_friendly_name,
            "voice_url": voice_url,
            "voice_method": voice_method,
        }

        _logger.info(
            "Creating TwiML Application: URL=%s voice_url=%s voice_method=%s",
            request_url,
            voice_url,
            voice_method,
        )
        try:
            app = client.applications.create(**payload)

            _logger.info(
                "TwiML Application created: URL=%s, status=%s, application_sid=%s",
                request_url,
                201,
                app.sid,
            )

            result = {
                "application_sid": app.sid,
                "voice_method": voice_method,
                "voice_url": voice_url,
                "application_friendly_name": friendly_name or self._default_application_friendly_name,
            }

            return result
        except TwilioRestException as e:
            _logger.error(
                "TwiML Application creation failed: URL=%s, status=%s, "
                "error_code=%s, error_message=%s",
                request_url,
                e.status,
                e.code,
                e.msg,
            )
            raise UserError(f"Failed to create TwiML Application:\n{str(e)}")
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Failed to create TwiML Application:\n{str(e)}")

    def update_twiml_application(self, client, application_sid, voice_url=None, voice_method=None):
        request_url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{client.username}/Applications/{application_sid}.json"
        )
        voice_url = voice_url or self._default_voice_url
        voice_method = voice_method or self._default_voice_method
        payload = {
            "voice_url": voice_url,
            "voice_method": voice_method,
        }
        _logger.info(
            "Updating TwiML Application: URL=%s voice_url=%s voice_method=%s",
            request_url,
            voice_url,
            voice_method,
        )
        try:
            app = client.applications(application_sid).update(**payload)
            _logger.info(
                "TwiML Application updated: URL=%s, status=%s, application_sid=%s",
                request_url,
                200,
                app.sid,
            )
            return {
                "application_sid": app.sid,
                "voice_method": voice_method,
                "voice_url": voice_url,
            }
        except TwilioRestException as e:
            _logger.error(
                "TwiML Application update failed: URL=%s, status=%s, "
                "error_code=%s, error_message=%s",
                request_url,
                e.status,
                e.code,
                e.msg,
            )
            raise UserError(f"Failed to update TwiML Application:\n{str(e)}")
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Failed to update TwiML Application:\n{str(e)}")

    def delete_api_key(self, client, api_key_sid):
        if not api_key_sid:
            return

        try:
            client.keys(api_key_sid).delete()
        except Exception as e:
            _logger.warning(
                "Failed to delete Twilio API Key '%s': %s",
                api_key_sid,
                str(e),
            )

    def delete_twiml_application(self, client, application_sid):
        if not application_sid:
            return

        try:
            client.applications(application_sid).delete()
        except Exception as e:
            _logger.warning(
                "Failed to delete TwiML Application '%s': %s",
                application_sid,
                str(e),
            )

    def generate_configuration(self, account_sid, auth_token, voice_url):
        try:
            client = self.get_client(account_sid, auth_token)
            api_key = self.generate_api_key(client)
            twiml_app = self.create_twiml_application(
                client,
                voice_url,
                voice_method=self._default_voice_method,
                friendly_name=self._default_application_friendly_name,
            )
            return {
                **api_key,
                **twiml_app,
                "voice_url": voice_url,
            }
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Failed to generate Twilio configuration:\n{str(e)}")

    def generate_access_token(self, env):
        ICP = env["ir.config_parameter"].sudo()

        account_sid = ICP.get_param("twilio_dialer.account_sid")
        api_key_sid = ICP.get_param("twilio_dialer.api_key_sid")
        api_secret = ICP.get_param("twilio_dialer.api_secret")
        application_sid = ICP.get_param("twilio_dialer.application_sid")

        missing = []
        if not account_sid:
            missing.append("Account SID")
        if not api_key_sid:
            missing.append("API Key SID")
        if not api_secret:
            missing.append("API Secret")
        if not application_sid:
            missing.append("Application SID")

        if missing:
            raise UserError(
                "Twilio configuration is incomplete. Missing: %s"
                % ", ".join(missing)
            )

        identity = "odoo_user_%s" % env.uid

        token = AccessToken(
            account_sid,
            api_key_sid,
            api_secret,
            identity=identity,
        )

        voice_grant = VoiceGrant(
            outgoing_application_sid=application_sid,
        )
        token.add_grant(voice_grant)

        return token.to_jwt()
