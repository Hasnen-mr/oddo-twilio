import logging
import re

import requests
from requests.auth import HTTPBasicAuth
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from odoo import models, fields
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

    def get_twilio_client(self, env=None):
        env = env or self.env
        ICP = env["ir.config_parameter"].sudo()
        account_sid = (ICP.get_param("twilio_dialer.account_sid") or "").strip()
        auth_token = (ICP.get_param("twilio_dialer.auth_token") or "").strip()

        if not account_sid or not auth_token:
            raise UserError("Twilio Account SID and Auth Token must be configured in Settings.")

        return self.get_client(account_sid, auth_token)

    def get_client(self, account_sid, auth_token):
        try:
            return Client(account_sid, auth_token)
        except Exception as e:
            raise UserError(f"Failed to initialize Twilio client:\n{str(e)}")

    def fetch_sms_history(self, phone, limit=50):
        """Centralized helper to fetch live SMS history for a phone number."""
        if not phone:
            return []
        client = self.get_twilio_client()

        # Fetch messages To recipient and From recipient
        messages_to = client.messages.list(to=phone, limit=limit)
        messages_from = client.messages.list(from_=phone, limit=limit)
        all_messages = messages_to + messages_from
        all_messages.sort(key=lambda m: m.date_created or m.date_sent)

        conversation = []
        for m in all_messages:
            is_inbound = "inbound" in (m.direction or "")
            conversation.append({
                "sid": m.sid,
                "body": m.body or "",
                "direction": "inbound" if is_inbound else "outbound",
                "from": m.from_ or "",
                "to": m.to or "",
                "status": m.status or "",
                "date": (m.date_created or m.date_sent).strftime("%Y-%m-%d %H:%M:%S") if (m.date_created or m.date_sent) else "",
            })
        return conversation

    def send_sms_message(self, recipient, body, partner_id=None):
        """Centralized helper to send an SMS via Twilio REST API and log Contact Chatter activity."""
        if not recipient or not body:
            raise UserError("Recipient phone number and message body are required.")

        from_number = self.get_twilio_phone_number()
        if not from_number:
            raise UserError("No valid Twilio phone number configured for sending SMS.")

        client = self.get_twilio_client()
        message = client.messages.create(
            from_=from_number,
            to=recipient,
            body=body,
        )

        # Contact Chatter activity
        partner = None
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            # Shared E.164 phone normalization matching
            digits = re.sub(r"\D", "", recipient)
            if digits:
                search_term = digits[-10:]
                partner = self.env["res.partner"].search([
                    "|", ("phone", "like", search_term), ("mobile", "like", search_term)
                ], limit=1)

        if partner:
            partner_name = partner.name or "Contact"
            chatter_body = (
                f"📤 Outgoing SMS To: {partner_name} ({recipient})\n"
                f"Message: {body}\n"
                f"Status: {message.status or 'queued'}"
            )
            partner.message_post(
                body=chatter_body,
                subject="Outgoing SMS",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

        return {
            "success": True,
            "sid": message.sid,
            "status": message.status or "sent",
            "message": "SMS sent successfully.",
        }

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
        if not phone_number:
            return ""
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
                    "type": "incoming",
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

    def get_outgoing_caller_ids(self, env=None):
        """Verified Outgoing Caller IDs that can be used as outbound caller ID."""
        env = env or self.env
        ICP = env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")

        if not account_sid or not auth_token:
            return []

        try:
            client = self.get_client(account_sid, auth_token)
            caller_ids = [
                {
                    "sid": record.sid,
                    "phone_number": record.phone_number,
                    "friendly_name": record.friendly_name,
                    "type": "outgoing_caller_id",
                }
                for record in client.outgoing_caller_ids.stream()
            ]
        except TwilioRestException as e:
            if e.status in (401, 403):
                _logger.warning("Twilio credentials invalid while listing outgoing caller IDs.")
                return []
            _logger.error("Twilio API error while retrieving outgoing caller IDs: %s", str(e))
            return []
        except Exception as e:
            _logger.error("Failed to retrieve Twilio outgoing caller IDs: %s", str(e))
            return []

        _logger.info("Found %s Twilio Outgoing Caller IDs.", len(caller_ids))
        return caller_ids

    def get_voice_url(self, env=None):
        ICP = (env or self.env)["ir.config_parameter"].sudo()

        stored = (ICP.get_param("twilio_dialer.voice_url") or "").strip()
        if stored and "/twilio_dialer/call_setup" not in stored:
            return stored

        base_url = (ICP.get_param("web.base.url") or "").rstrip("/")

        # localhost should not be sent to Twilio
        if (
            not base_url
            or "localhost" in base_url
            or "127.0.0.1" in base_url
        ):
            return None

        return f"{base_url}/twilio_dialer/call_setup"

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
        }

        if voice_url:
            payload["voice_url"] = voice_url
            payload["voice_method"] = voice_method or self._default_voice_method

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

    def fetch_recordings_by_call_sid(self, call_sid):
        ICP = self.env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")
        if not account_sid or not auth_token:
            _logger.warning("fetch_recordings_by_call_sid: Twilio credentials not configured")
            return []

        try:
            client = self.get_client(account_sid, auth_token)
            _logger.info("Fetching Twilio recordings for call_sid=%s", call_sid)
            recordings = client.calls(call_sid).recordings.list(limit=1)
            _logger.info(
                "Twilio returned %d recording(s) for call_sid=%s",
                len(recordings), call_sid,
            )
            return recordings
        except TwilioRestException as e:
            _logger.warning("Twilio recordings fetch failed for %s: %s", call_sid, e)
            return []
        except Exception as e:
            _logger.warning("Failed to fetch Twilio recordings for %s: %s", call_sid, e)
            return []

    def fetch_recording_audio(self, recording_sid):
        ICP = self.env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")
        if not account_sid or not auth_token:
            return None, None

        url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{account_sid}/Recordings/{recording_sid}.wav"
        )
        try:
            resp = requests.get(
                url,
                auth=HTTPBasicAuth(account_sid, auth_token),
                timeout=30,
                stream=True,
            )
        except requests.RequestException:
            _logger.exception("Failed to fetch recording %s from Twilio", recording_sid)
            return None, None

        if resp.status_code != 200:
            resp.close()
            return None, None

        content_type = resp.headers.get("Content-Type", "audio/wav")
        return resp, content_type

    def fetch_transcriptions_by_call_sid(self, call_sid):
        """Fetch transcriptions for a specific call from Twilio.

        The Twilio REST API does not provide a /Calls/{CallSid}/Transcriptions endpoint.
        Transcriptions are associated with Recordings or the account-wide Transcriptions
        resource. This function therefore:
          1. Fetches recordings for the given Call SID (client.calls(call_sid).recordings.list())
          2. For each recording, lists transcriptions under that recording
             (client.recordings(recording_sid).transcriptions.list())

        Returns a list of transcription objects (may be empty). Does not suppress
        exceptions: TwilioRestException or other exceptions are logged and re-raised
        so callers can handle/fail as appropriate.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")
        if not account_sid or not auth_token:
            _logger.warning("fetch_transcriptions_by_call_sid: Twilio credentials not configured")
            return []

        client = self.get_client(account_sid, auth_token)
        _logger.info("Starting transcription fetch for call_sid=%s", call_sid)

        results = []
        try:
            # Step 1: fetch recordings for the call
            _logger.info("Requesting recordings for call_sid=%s", call_sid)
            recordings = client.calls(call_sid).recordings.list()
            _logger.info("Twilio returned %d recording(s) for call_sid=%s", len(recordings), call_sid)

            if not recordings:
                _logger.info("No recordings found for call_sid=%s; therefore no transcriptions available", call_sid)
                return []

            # Step 2: for each recording, fetch associated transcriptions
            for rec in recordings:
                recording_sid = getattr(rec, "sid", None) or ""
                rec_status = getattr(rec, "status", None)
                rec_duration = getattr(rec, "duration", None)
                _logger.info(
                    "Checking transcriptions for call_sid=%s recording_sid=%s status=%s duration=%s",
                    call_sid,
                    recording_sid,
                    rec_status,
                    rec_duration,
                )

                transcriptions = client.recordings(recording_sid).transcriptions.list()
                # Log the raw response summary
                try:
                    transcription_summaries = [
                        {
                            "sid": getattr(t, "sid", None),
                            "status": (getattr(t, "status", None) or "").lower(),
                            "recording_sid": getattr(t, "recording_sid", None),
                            "transcription_text_present": bool(getattr(t, "transcription_text", None) or getattr(t, "transcription_text", None) == ""),
                        }
                        for t in transcriptions
                    ]
                except Exception:
                    transcription_summaries = [str(t) for t in transcriptions]

                _logger.info(
                    "Twilio returned %d transcription(s) for recording_sid=%s: %s",
                    len(transcriptions), recording_sid, transcription_summaries,
                )

                if not transcriptions:
                    # No transcriptions for this recording — log possible reasons available from recording
                    _logger.info(
                        "No transcriptions found for recording_sid=%s (call_sid=%s). recording_status=%s recording_duration=%s",
                        recording_sid,
                        call_sid,
                        rec_status,
                        rec_duration,
                    )
                    # Continue to next recording; do not raise here
                    continue

                # Collect transcription objects to return — caller will inspect status/text
                for t in transcriptions:
                    _logger.info(
                        "Found transcription for call_sid=%s recording_sid=%s transcription_sid=%s status=%s",
                        call_sid,
                        recording_sid,
                        getattr(t, "sid", None),
                        (getattr(t, "status", None) or "").lower(),
                    )
                    results.append(t)

            return results

        except TwilioRestException as e:
            # Log full exception details and re-raise (do not suppress)
            _logger.exception("Twilio REST error while fetching transcriptions for call_sid=%s: %s", call_sid, e)
            raise
        except Exception as e:
            # Log and re-raise any other unexpected exceptions
            _logger.exception("Unexpected error while fetching transcriptions for call_sid=%s: %s", call_sid, e)
            raise

    def get_transcript_text(self, transcription):
        """Extract transcript text from a Twilio transcription object.
        
        Returns the text content or empty string if not available.
        """
        if not transcription:
            return ""
        text = getattr(transcription, "text_content", "") or ""
        return text.strip()

    def ensure_voice_credentials(self, env, force_refresh=False):
        """Ensure API key + TwiML app exist in Twilio; recreate if missing/stale.

        Used when AccessTokenInvalid (20101) occurs because stored keys/apps
        were deleted in the Twilio console.
        """
        ICP = env["ir.config_parameter"].sudo()
        account_sid = (ICP.get_param("twilio_dialer.account_sid") or "").strip()
        auth_token = (ICP.get_param("twilio_dialer.auth_token") or "").strip()
        api_key_sid = (ICP.get_param("twilio_dialer.api_key_sid") or "").strip()
        api_secret = (ICP.get_param("twilio_dialer.api_secret") or "").strip()
        application_sid = (ICP.get_param("twilio_dialer.application_sid") or "").strip()

        if not account_sid or not auth_token:
            raise UserError(
                "Twilio Account SID and Auth Token are required. "
                "Open Configuration and save your credentials."
            )

        client = self.get_client(account_sid, auth_token)
        changed = False

        need_new_api_key = force_refresh or not api_key_sid or not api_secret
        if not need_new_api_key:
            try:
                client.keys(api_key_sid).fetch()
            except TwilioRestException as err:
                if err.status == 404:
                    _logger.warning(
                        "Twilio API Key %s not found; regenerating.", api_key_sid
                    )
                    need_new_api_key = True
                else:
                    raise UserError(
                        "Unable to verify Twilio API Key:\n%s" % err
                    ) from err

        if need_new_api_key:
            api_key = self.generate_api_key(client)
            api_key_sid = api_key["api_key_sid"]
            api_secret = api_key["api_secret"]
            ICP.set_param("twilio_dialer.api_key_sid", api_key_sid)
            ICP.set_param("twilio_dialer.api_secret", api_secret)
            ICP.set_param(
                "twilio_dialer.api_key_friendly_name",
                api_key.get("api_key_friendly_name", ""),
            )
            changed = True

        voice_url = self.get_voice_url(env) or self._default_voice_url
        # Recreate TwiML app only when missing or deleted (not on every token refresh).
        need_new_app = not application_sid
        if not need_new_app:
            try:
                client.applications(application_sid).fetch()
            except TwilioRestException as err:
                if err.status == 404:
                    _logger.warning(
                        "TwiML Application %s not found; recreating.",
                        application_sid,
                    )
                    need_new_app = True
                else:
                    raise UserError(
                        "Unable to verify TwiML Application:\n%s" % err
                    ) from err

        if need_new_app:
            twiml_app = self.create_twiml_application(
                client,
                voice_url,
                voice_method=self._default_voice_method,
            )
            application_sid = twiml_app["application_sid"]
            ICP.set_param("twilio_dialer.application_sid", application_sid)
            ICP.set_param(
                "twilio_dialer.application_friendly_name",
                twiml_app.get("application_friendly_name", ""),
            )
            ICP.set_param(
                "twilio_dialer.voice_method",
                twiml_app.get("voice_method", self._default_voice_method),
            )
            ICP.set_param("twilio_dialer.voice_url", voice_url)
            changed = True

        return {
            "changed": changed,
            "account_sid": account_sid,
            "api_key_sid": api_key_sid,
            "api_secret": api_secret,
            "application_sid": application_sid,
        }

    def generate_access_token(self, env, force_refresh=False):
        ICP = env["ir.config_parameter"].sudo()

        account_sid = (ICP.get_param("twilio_dialer.account_sid") or "").strip()
        api_key_sid = (ICP.get_param("twilio_dialer.api_key_sid") or "").strip()
        api_secret = (ICP.get_param("twilio_dialer.api_secret") or "").strip()
        application_sid = (ICP.get_param("twilio_dialer.application_sid") or "").strip()

        incomplete = not all([account_sid, api_key_sid, api_secret, application_sid])
        if force_refresh or incomplete:
            creds = self.ensure_voice_credentials(env, force_refresh=force_refresh)
            account_sid = creds["account_sid"]
            api_key_sid = creds["api_key_sid"]
            api_secret = creds["api_secret"]
            application_sid = creds["application_sid"]

        identity = "id_odoo_%s" % account_sid

        token = AccessToken(
            account_sid,
            api_key_sid,
            api_secret,
            identity=identity,
        )

        voice_grant = VoiceGrant(
            outgoing_application_sid=application_sid,
            incoming_allow=True,  # Required: allows the browser Device to receive incoming calls
        )
        token.add_grant(voice_grant)

        return token.to_jwt()

    def configure_incoming_phone_number(self, phone_number=None, env=None):
        """Assign the stored TwiML Application SID to every Twilio Incoming Phone Number.

        When Incoming Calls is enabled, each account phone number is updated with
        ``voice_application_sid`` from ``twilio_dialer.application_sid`` so Twilio
        routes voice through the Odoo TwiML Application.
        """
        env = env or self.env
        ICP = env["ir.config_parameter"].sudo()
        account_sid = ICP.get_param("twilio_dialer.account_sid")
        auth_token = ICP.get_param("twilio_dialer.auth_token")
        application_sid = (ICP.get_param("twilio_dialer.application_sid") or "").strip()

        if not account_sid or not auth_token:
            _logger.warning(
                "configure_incoming_phone_number: Account SID or Auth Token missing."
            )
            return False

        if not application_sid:
            _logger.warning(
                "configure_incoming_phone_number: TwiML Application SID missing in Odoo."
            )
            return False

        try:
            client = self.get_client(account_sid, auth_token)
            numbers = list(client.incoming_phone_numbers.stream())
            if not numbers:
                _logger.warning(
                    "configure_incoming_phone_number: No Incoming Phone Numbers found "
                    "in Twilio account %s",
                    account_sid,
                )
                return False

            updated = 0
            skipped = 0
            for number in numbers:
                number_sid = getattr(number, "sid", "") or ""
                phone = getattr(number, "phone_number", "") or ""
                current_app = (getattr(number, "voice_application_sid", None) or "").strip()

                if current_app == application_sid:
                    skipped += 1
                    _logger.info(
                        "Phone number %s (%s) already has Application SID %s",
                        phone,
                        number_sid,
                        application_sid,
                    )
                    continue

                _logger.info(
                    "Assigning Application SID %s to phone number %s (%s)",
                    application_sid,
                    phone,
                    number_sid,
                )
                number.update(voice_application_sid=application_sid)
                updated += 1

            _logger.info(
                "Incoming call Application assign complete: updated=%s skipped=%s total=%s app=%s",
                updated,
                skipped,
                len(numbers),
                application_sid,
            )
            return True

        except TwilioRestException as e:
            _logger.error(
                "Twilio REST API error while assigning Application SID to phone numbers: %s",
                e,
            )
            raise UserError(
                "Twilio API error while assigning Application to phone numbers:\n%s" % e
            )
        except UserError:
            raise
        except Exception as e:
            _logger.exception(
                "Unexpected error while assigning Application SID to phone numbers: %s",
                e,
            )
            raise UserError(
                "Failed to assign TwiML Application to Twilio phone numbers:\n%s" % e
            )
