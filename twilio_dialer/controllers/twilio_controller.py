import json
import logging
from xml.sax.saxutils import escape

from odoo import http
from odoo.exceptions import UserError, AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)


class TwilioController(http.Controller):

    @http.route("/twilio_dialer/token", type="http", auth="user", methods=["GET"])
    def get_token(self, **kwargs):
        try:
            token = request.env["twilio.service"].generate_access_token(request.env)
            return request.make_json_response({"success": True, "token": token})
        except Exception as e:
            _logger.error("Failed to generate Twilio access token: %s", str(e))
            return request.make_json_response(
                {"success": False, "message": str(e)}, status=400
            )

    @http.route("/twilio_dialer/phone_number", type="json", auth="user")
    def get_phone_number(self):
        try:
            service = request.env["twilio.service"]
            phone_number = service.get_twilio_phone_number()
            icp = request.env["ir.config_parameter"].sudo()
            try:
                phone_numbers = json.loads(
                    icp.get_param("twilio_dialer.incoming_phone_numbers", "[]")
                )
            except (TypeError, json.JSONDecodeError):
                phone_numbers = []

            if not phone_numbers:
                phone_numbers = service.get_incoming_phone_numbers()

            return {
                "phone_number": phone_number,
                "phone_numbers": phone_numbers,
            }
        except UserError as e:
            return {
                "phone_number": False,
                "phone_numbers": [],
                "message": str(e),
            }

    @http.route(
        "/twilio_dialer/call_setup",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def call_setup(self, **kwargs):
        try:
            caller_id = (
                kwargs.get("From")
                or kwargs.get("from")
                or kwargs.get("from_number")
                or kwargs.get("CallerId")
                or kwargs.get("callerId")
                or request.httprequest.args.get("From", "")
                or request.httprequest.args.get("from", "")
                or request.httprequest.args.get("from_number", "")
                or request.httprequest.args.get("CallerId", "")
                or request.httprequest.args.get("callerId", "")
            )
            if not caller_id:
                caller_id = request.env["twilio.service"].get_verified_twilio_phone_number()

            to_number = (
                kwargs.get("To")
                or kwargs.get("to")
                or request.httprequest.args.get("To", "")
                or request.httprequest.args.get("to", "")
            )

            if not to_number:
                raise UserError("Missing destination number for Twilio outbound call.")

            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Dial callerId="{caller_id}"><Number>{to_number}</Number></Dial></Response>'
            ).format(
                caller_id=escape(caller_id),
                to_number=escape(to_number),
            )
            return request.make_response(
                twiml,
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )
        except Exception as e:
            _logger.error("Twilio call setup failed: %s", str(e))
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Say>The Twilio caller ID is not configured correctly.</Say></Response>'
            )
            return request.make_response(
                twiml,
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )

    @http.route("/twilio_dialer/call_log/create", type="json", auth="user")
    def create_call_log(self, call_sid, to_number, partner_id=False):
        call_log = request.env["twilio.call.log"].create_outgoing_call(
            call_sid,
            to_number,
            partner_id=partner_id,
        )
        return {"id": call_log.id}

    @http.route("/twilio_dialer/call_log/update", type="json", auth="user")
    def update_call_log(self, call_sid, status):
        request.env["twilio.call.log"].update_call_status(call_sid, status)
        return {"success": True}

    @http.route("/twilio_dialer/billing", type="json", auth="user")
    def get_billing(self):
        try:
            return {"success": True, "billing": request.env["twilio.billing.service"].get_billing()}
        except UserError as error:
            return {"success": False, "message": str(error)}

    @http.route("/twilio_dialer/recording/<int:call_log_id>", type="http", auth="user", methods=["GET"])
    def get_recording(self, call_log_id, **kwargs):
        _logger.info("Recording request for call_log_id=%s", call_log_id)
        call_log = request.env["twilio.call.log"].browse(call_log_id)
        if not call_log.exists() or not call_log.recording_sid:
            _logger.warning(
                "Recording access denied for call_log_id=%s: exists=%s recording_sid=%s",
                call_log_id, call_log.exists(),
                call_log.recording_sid if call_log.exists() else "N/A",
            )
            raise AccessDenied()

        _logger.info(
            "Fetching recording audio for call_log_id=%s recording_sid=%s",
            call_log_id, call_log.recording_sid,
        )
        resp, content_type = request.env["twilio.service"].fetch_recording_audio(
            call_log.recording_sid
        )
        if resp is None:
            _logger.warning(
                "Recording audio not available for call_log_id=%s recording_sid=%s",
                call_log_id, call_log.recording_sid,
            )
            return request.make_response("Recording not available", status=404)

        _logger.info(
            "Serving recording for call_log_id=%s content_type=%s",
            call_log_id, content_type,
        )

        def generate():
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                resp.close()

        headers = [
            ("Content-Type", content_type),
            ("Content-Disposition", 'inline; filename="%s.wav"' % call_log.recording_sid),
            ("Cache-Control", "private, max-age=3600"),
        ]
        return request.make_response(generate(), headers=headers)

    @http.route(
        "/twilio_dialer/incoming_call",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def incoming_call(self, **kwargs):
        """Handle Twilio incoming call webhook and return TwiML.

        Behavior is driven by the external MyBroadcast call settings when available
        and falls back to ir.config_parameter values for AI/transcription flags.
        """
        try:
            # Normalize parameters from Twilio
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            call_sid = params.get("CallSid") or params.get("CallSid") or params.get("CallSid")
            from_number = params.get("From") or params.get("from") or ""
            to_number = params.get("To") or params.get("to") or ""

            _logger.info("Incoming call webhook received: CallSid=%s From=%s To=%s", call_sid, from_number, to_number)

            # Create a call log before answering so other workers can reference it
            call_log = request.env["twilio.call.log"].sudo().create_incoming_call(call_sid, from_number, to_number)

            # Read settings: prefer external MyBroadcast API for routing/record/voicemail
            icp = request.env["ir.config_parameter"].sudo()
            account_sid = icp.get_param("twilio_dialer.account_sid")
            incoming = {}
            if account_sid:
                try:
                    from ..services import MyBroadcastAPI
                    payload = MyBroadcastAPI().get_call_settings(account_sid)
                    # Use the settings parser from res.config.settings if available
                    settings_model = request.env["res.config.settings"].sudo()
                    incoming_vals, outgoing_vals, error = settings_model._parse_call_settings(payload)
                    if not error:
                        incoming = incoming_vals
                except Exception:
                    _logger.exception("Failed to fetch MyBroadcast call settings, falling back to config parameters")

            # Fallback to ir.config_parameter for transcription flag
            enable_transcription = icp.get_param("twilio_dialer.incoming_transcription") in ("True", "true", "1")
            # Decide routing
            allow = incoming.get("allow", True) if isinstance(incoming, dict) else True
            record_call = incoming.get("record", False) if isinstance(incoming, dict) else False
            forward = incoming.get("forward", False) if isinstance(incoming, dict) else False
            forward_to = incoming.get("forwardTo", "") if isinstance(incoming, dict) else ""
            voicemail = incoming.get("voicemail", False) if isinstance(incoming, dict) else False
            voicemail_text = incoming.get("voicemailText", "") if isinstance(incoming, dict) else ""

            # If incoming calls are not allowed, reject
            if not allow:
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>'
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            caller_id = icp.get_param("twilio_dialer.phone_number") or None

            # Build TwiML response based on routing settings
            if forward and forward_to:
                # If forward_to looks like a phone number (digits, +), dial number
                if isinstance(forward_to, str) and forward_to.strip() and any(ch.isdigit() for ch in forward_to):
                    number = escape(forward_to)
                    record_attr = " record=\"record-from-answer-dual\"" if record_call else ""
                    twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                             '<Response><Dial callerId="{caller_id}"{record}>{number}</Dial></Response>').format(
                        caller_id=escape(caller_id) if caller_id else "",
                        record=record_attr,
                        number=number,
                    )
                    return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})
                else:
                    # Forward to client/device — fall back to dialing a default client id
                    client_id = escape(str(forward_to)) if forward_to else "agent"
                    record_attr = " record=\"record-from-answer-dual\"" if record_call else ""
                    twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                             '<Response><Dial callerId="{caller_id}"{record}><Client>{client}</Client></Dial></Response>').format(
                        caller_id=escape(caller_id) if caller_id else "",
                        record=record_attr,
                        client=client_id,
                    )
                    return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            if voicemail:
                # Answer and record voicemail
                say = escape(voicemail_text) if voicemail_text else "Please leave a message after the tone."
                twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                         '<Response><Say>{say}</Say><Record maxLength="120" playBeep="true"/></Response>').format(say=say)
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            # Default answer: simple <Say> then hangup to avoid charge if not routed
            twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                     '<Response><Say>Thank you for calling. Please try again later.</Say><Hangup/></Response>')
            return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})
        except Exception as e:
            _logger.exception("Incoming call handling failed: %s", e)
            twiml = ('<?xml version="1.0" encoding="UTF-8"?>'
                     '<Response><Say>We are unable to handle this call right now.</Say><Hangup/></Response>')
            return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

    @http.route(
        "/twilio_dialer/twilio_event",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def twilio_event(self, **kwargs):
        """Handle Twilio status/recording callbacks and update call logs.

        This route accepts CallSid, CallStatus, RecordingSid, RecordingUrl, RecordingStatus
        and updates the corresponding twilio.call.log record. It reuses the existing
        update_call_status and recording sync logic.
        """
        try:
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            call_sid = params.get("CallSid") or params.get("callSid") or params.get("CallSid")
            call_status = params.get("CallStatus") or params.get("callStatus") or params.get("CallStatus")
            recording_sid = params.get("RecordingSid") or params.get("recordingSid")
            recording_status = params.get("RecordingStatus") or params.get("recordingStatus")

            _logger.info("Twilio event received: CallSid=%s CallStatus=%s RecordingSid=%s RecordingStatus=%s",
                         call_sid, call_status, recording_sid, recording_status)

            if call_sid and call_status:
                # Normalize Twilio status to model statuses
                normalized = (call_status or "").lower().replace("-", "_")
                try:
                    request.env["twilio.call.log"].sudo().update_call_status(call_sid, normalized)
                except Exception:
                    _logger.exception("Failed to update call status for CallSid=%s", call_sid)

            if call_sid and recording_sid:
                try:
                    # Write recording directly; recording worker will also attempt sync but writing here speeds persistence
                    log = request.env["twilio.call.log"].sudo().search([("call_sid", "=", call_sid)], limit=1)
                    if log:
                        vals = {"recording_sid": recording_sid}
                        if recording_status:
                            status_map = {"completed": "completed", "in-progress": "recording", "processing": "pending", "failed": "failed"}
                            vals["recording_status"] = status_map.get((recording_status or "").lower(), "completed")
                        log.write(vals)
                except Exception:
                    _logger.exception("Failed to record recording callback for CallSid=%s RecordingSid=%s", call_sid, recording_sid)

            return request.make_response("", headers={"Content-Type": "text/plain"})
        except Exception:
            _logger.exception("Unhandled error in twilio_event")
            return request.make_response("", status=500)

