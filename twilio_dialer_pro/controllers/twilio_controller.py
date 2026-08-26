import json
import logging
import re
from xml.sax.saxutils import escape

from odoo import fields, http
from odoo.exceptions import UserError, AccessDenied
from odoo.http import request

try:
    from twilio.twiml.voice_response import VoiceResponse, Dial, Client, Say, Record, Reject, Hangup
    _TWILIO_TWIML_AVAILABLE = True
except ImportError:
    _TWILIO_TWIML_AVAILABLE = False

try:
    from twilio.request_validator import RequestValidator
    _TWILIO_VALIDATOR_AVAILABLE = True
except ImportError:
    _TWILIO_VALIDATOR_AVAILABLE = False

_logger = logging.getLogger(__name__)


class TwilioController(http.Controller):
    def _validate_twilio_request(self):
        """Cryptographically validates incoming webhook requests using X-Twilio-Signature and Auth Token."""
        if not _TWILIO_VALIDATOR_AVAILABLE:
            _logger.error("Twilio RequestValidator module is not available.")
            return False

        try:
            auth_token = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("twilio_dialer.auth_token")
                or ""
            ).strip()
            if not auth_token:
                _logger.error("Twilio Webhook validation failed: Auth Token not configured.")
                return False

            signature = request.httprequest.headers.get("X-Twilio-Signature", "").strip()
            if not signature:
                _logger.warning("Twilio Webhook rejected: Missing X-Twilio-Signature header.")
                return False

            validator = RequestValidator(auth_token)

            # Collect parameters (Form for POST, Args for GET)
            if request.httprequest.method == "POST":
                params = dict(request.httprequest.form)
            else:
                params = dict(request.httprequest.args)

            # Candidate 1: Standard reconstruction from headers (respecting reverse proxies)
            proto = request.httprequest.headers.get("X-Forwarded-Proto", request.httprequest.scheme or "https")
            host = request.httprequest.headers.get("X-Forwarded-Host", request.httprequest.host)
            path = request.httprequest.full_path or request.httprequest.path
            candidate_url1 = f"{proto}://{host}{path}"

            if validator.validate(candidate_url1, params, signature):
                return True

            # Candidate 2: Using configured web.base.url
            base_url = (request.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
            if base_url:
                candidate_url2 = f"{base_url}{path}"
                if validator.validate(candidate_url2, params, signature):
                    return True

            # Candidate 3: Direct request URL
            direct_url = request.httprequest.url
            if direct_url and direct_url not in (candidate_url1, candidate_url2 if base_url else None):
                if validator.validate(direct_url, params, signature):
                    return True

            _logger.warning("Twilio Webhook rejected: Invalid X-Twilio-Signature.")
            return False
        except Exception as e:
            _logger.error(f"Error during Twilio signature validation: {e}")
            return False


    @http.route("/twilio_dialer/billing", type="json", auth="user")
    def get_billing_info(self, **kwargs):
        """Fetch billing information for the active Twilio account."""
        try:
            from ..services import MyBroadcastAPI, MyBroadcastAPIError
            icp = request.env["ir.config_parameter"].sudo()
            account_sid = icp.get_param("twilio_dialer.account_sid") or ""
            if not account_sid:
                return {"success": False, "message": "No active Twilio account connected."}
            api = MyBroadcastAPI()
            return api.get_billing(account_sid)
        except Exception as e:
            _logger.warning("Failed to fetch billing info: %s", e)
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/token", type="http", auth="user", methods=["GET"])
    def get_token(self, **kwargs):
        """Return a Voice Access Token.

        Pass refresh=1 (or regenerate=1) to recreate API key / TwiML app when
        Twilio rejects the token (AccessTokenInvalid 20101).
        """
        try:
            force_refresh = str(
                kwargs.get("refresh") or kwargs.get("regenerate") or ""
            ).lower() in ("1", "true", "yes")
            service = request.env["twilio.service"]
            token = service.generate_access_token(
                request.env, force_refresh=force_refresh
            )
            return request.make_json_response({
                "success": True,
                "token": token,
                "regenerated": force_refresh,
            })
        except Exception as e:
            _logger.error("Failed to generate Twilio access token: %s", str(e))
            return request.make_json_response(
                {"success": False, "message": str(e)}, status=400
            )

    @http.route("/twilio_dialer/phone_number", type="json", auth="user")
    def get_phone_number(self):
        try:
            service = request.env["twilio.service"]
            icp = request.env["ir.config_parameter"].sudo()
            account_sid = icp.get_param("twilio_dialer.account_sid") or ""
            
            if not account_sid:
                return {
                    "phone_number": False,
                    "phone_numbers": [],
                    "message": "No active Twilio account connected.",
                }

            # Fetch fresh incoming phone numbers live from Twilio API for active account
            phone_numbers = service.get_incoming_phone_numbers() or []

            valid_numbers = []
            for item in phone_numbers:
                if isinstance(item, dict) and item.get("phone_number"):
                    if not item.get("type"):
                        item["type"] = "incoming"
                    valid_numbers.append(item)

            phone_numbers = valid_numbers

            # Sync twilio.phone.number DB records safely without raising AttributeError
            db_numbers = request.env["twilio.phone.number"].sudo().search([])
            existing_db_nums = {n.phone_number for n in db_numbers}
            for item in phone_numbers:
                p_num = item.get("phone_number")
                f_name = item.get("friendly_name") or p_num
                if p_num and p_num not in existing_db_nums:
                    request.env["twilio.phone.number"].sudo().create({
                        "phone_number": p_num,
                        "friendly_name": f_name,
                        "display_name": f"{f_name} ({p_num})",
                    })
                    existing_db_nums.add(p_num)

            seen = {item.get("phone_number") for item in phone_numbers if item.get("phone_number")}

            for caller_id in service.get_outgoing_caller_ids():
                number = caller_id.get("phone_number")
                if not number or number in seen:
                    continue
                seen.add(number)
                phone_numbers.append(caller_id)

            phone_number = phone_numbers[0]["phone_number"] if phone_numbers else False

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
        except Exception as e:
            _logger.exception("Error in get_phone_number: %s", str(e))
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
        if not self._validate_twilio_request():
            return Response("Forbidden: Invalid Twilio Signature", status=403, content_type="text/plain")
        try:
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            direction = (
                params.get("Direction")
                or params.get("direction")
                or request.httprequest.args.get("Direction", "")
                or ""
            ).lower()

            caller_param = (
                params.get("Caller")
                or params.get("caller")
                or params.get("From")
                or params.get("from")
                or ""
            )
            is_client_call = (
                str(caller_param).strip().lower().startswith("client:")
                or bool(params.get("ApplicationSid"))
                or bool(params.get("destination"))
                or bool(params.get("phone"))
            )

            if direction.startswith("inbound") and not is_client_call:
                return self.incoming_call(**kwargs)

            raw_caller_id = (
                params.get("CallerId")
                or params.get("callerId")
                or params.get("from_number")
                or params.get("From")
                or params.get("from")
                or request.httprequest.args.get("CallerId", "")
                or request.httprequest.args.get("from_number", "")
                or request.httprequest.args.get("From", "")
                or ""
            )

            def _sanitize_e164(raw):
                if not raw or str(raw).startswith("client:"):
                    return ""
                s = str(raw).strip()
                if s in ("ALL", "All numbers"):
                    return ""
                matches = re.findall(r"\+[1-9]\d{9,14}", s)
                if matches:
                    return matches[-1]
                digits = re.sub(r"\D", "", s)
                if digits and len(digits) >= 10:
                    clean = digits[-11:] if len(digits) >= 11 else digits[-10:]
                    return "+" + clean if len(clean) == 11 else "+1" + clean
                return ""

            caller_id = _sanitize_e164(raw_caller_id)
            if not caller_id or not caller_id.startswith("+"):
                caller_id = request.env["twilio.service"].sudo().get_verified_twilio_phone_number()

            to_raw = (
                params.get("To")
                or params.get("to")
                or params.get("destination")
                or params.get("phone")
                or request.httprequest.args.get("To", "")
                or request.httprequest.args.get("to", "")
                or request.httprequest.args.get("destination", "")
                or request.httprequest.args.get("phone", "")
            )

            to_number = _sanitize_e164(to_raw)
            if not to_number:
                digits_to = re.sub(r"\D", "", str(to_raw or ""))
                if digits_to:
                    to_number = "+" + digits_to if not str(to_raw).startswith("+") else "+" + digits_to

            if not to_number:
                raise UserError("Missing destination number for Twilio outbound call.")

            if _TWILIO_TWIML_AVAILABLE:
                response = VoiceResponse()
                dial = Dial(caller_id=caller_id)
                dial.number(to_number)
                response.append(dial)
                return request.make_response(
                    str(response),
                    headers=[("Content-Type", "text/xml")],
                )
            else:
                xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Dial callerId="{caller_id}"><Number>{to_number}</Number></Dial></Response>'
                return request.make_response(
                    xml,
                    headers=[("Content-Type", "application/xml")],
                )
        except Exception as e:
            _logger.error("Call setup error: %s", str(e))
            xml_err = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred setting up the call.</Say><Hangup/></Response>'
            return request.make_response(
                xml_err,
                headers=[("Content-Type", "application/xml")],
            )

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
        if not self._validate_twilio_request():
            return Response("Forbidden: Invalid Twilio Signature", status=403, content_type="text/plain")
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
            allow = incoming.get("allow", True) if isinstance(incoming, dict) and "allow" in incoming else True
            record_call = incoming.get("record", False) if isinstance(incoming, dict) and "record" in incoming else (
                icp.get_param("twilio_dialer.incoming_record") in ("True", "true", "1") or
                icp.get_param("twilio_dialer.record_calls") in ("True", "true", "1")
            )
            forward = incoming.get("forward", False) if isinstance(incoming, dict) else False
            forward_to = incoming.get("forwardTo", "") if isinstance(incoming, dict) else ""
            voicemail = incoming.get("voicemail", False) if isinstance(incoming, dict) else False
            voicemail_text = incoming.get("voicemailText", "") if isinstance(incoming, dict) else ""
            welcome_greeting = incoming.get("welcomeGreeting", incoming.get("welcome", False)) if isinstance(incoming, dict) else False
            welcome_greeting_text = (
                incoming.get("welcomeGreetingText", incoming.get("welcomeText", ""))
                if isinstance(incoming, dict)
                else ""
            )
            # Fallback to locally persisted greeting values
            if not welcome_greeting:
                welcome_greeting = icp.get_param("twilio_dialer.incoming_welcome_greeting") in (
                    "True",
                    "true",
                    "1",
                )
            if not welcome_greeting_text:
                welcome_greeting_text = icp.get_param(
                    "twilio_dialer.incoming_welcome_greeting_text",
                    "",
                ) or ""

            # If incoming calls are not allowed, reject
            if not allow:
                twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>'
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            caller_id = icp.get_param("twilio_dialer.phone_number") or None
            greeting_say = ""
            if welcome_greeting:
                greeting_say = (
                    welcome_greeting_text.strip()
                    if isinstance(welcome_greeting_text, str) and welcome_greeting_text.strip()
                    else "Thank you for calling. Please wait while we connect you."
                )

            # Build TwiML response based on routing settings
            if forward and forward_to and isinstance(forward_to, str) and forward_to.strip() and any(ch.isdigit() for ch in forward_to):
                # Forward to external phone number
                number = escape(forward_to)
                record_attr = ' record="record-from-answer-dual"' if record_call else ""
                say_xml = f"<Say>{escape(greeting_say)}</Say>" if greeting_say else ""
                twiml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response>{say}<Dial callerId="{caller_id}" answerOnBridge="true"{record}>{number}</Dial></Response>'
                ).format(
                    say=say_xml,
                    caller_id=escape(caller_id or from_number or ""),
                    record=record_attr,
                    number=number,
                )
                _logger.info("[Twilio Incoming] TwiML generated (Forward Number): %s", twiml)
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            if voicemail and not forward:
                # Answer and record voicemail
                say = escape(voicemail_text) if voicemail_text else "Please leave a message after the tone."
                greet_xml = f"<Say>{escape(greeting_say)}</Say>" if greeting_say else ""
                twiml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response>{greet}<Say>{say}</Say><Record maxLength="120" playBeep="true"/></Response>'
                ).format(greet=greet_xml, say=say)
                _logger.info("[Twilio Incoming] TwiML generated (Voicemail): %s", twiml)
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            # Default routing: Dial the browser VoIP Client identity matching JWT ("id_odoo_{account_sid}")
            client_identity = f"id_odoo_{account_sid}" if account_sid else "agent"
            caller_id_val = from_number or icp.get_param("twilio_dialer.phone_number") or ""

            if _TWILIO_TWIML_AVAILABLE:
                # Use the official twilio-python SDK â€” guaranteed schema-correct TwiML
                response = VoiceResponse()
                if greeting_say:
                    response.say(greeting_say)
                dial = Dial(
                    caller_id=caller_id_val,
                    answer_on_bridge=True,
                    action="/twilio_dialer/twilio_event",
                    record="record-from-answer-dual" if record_call else None,
                )
                dial.client(client_identity)
                response.append(dial)
                twiml = str(response)
            else:
                # Fallback: manual construction (plain text-content form â€” valid per Twilio docs)
                record_attr = ' record="record-from-answer-dual"' if record_call else ""
                say_xml = f"<Say>{escape(greeting_say)}</Say>" if greeting_say else ""
                twiml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response>'
                    '{say}'
                    '<Dial callerId="{caller_id}" answerOnBridge="true" action="/twilio_dialer/twilio_event"{record}>'
                    '<Client>{client}</Client>'
                    '</Dial>'
                    '</Response>'
                ).format(
                    say=say_xml,
                    caller_id=escape(caller_id_val),
                    record=record_attr,
                    client=escape(client_identity),
                )

            _logger.info("[Twilio Incoming] TwiML (Browser Client %s): %s", client_identity, twiml)
            return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})
        except Exception as e:
            _logger.exception("Incoming call handling failed: %s", e)
            if _TWILIO_TWIML_AVAILABLE:
                err_resp = VoiceResponse()
                err_resp.say("We are unable to handle this call right now.")
                err_resp.hangup()
                twiml = str(err_resp)
            else:
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
        if not self._validate_twilio_request():
            return Response("Forbidden: Invalid Twilio Signature", status=403, content_type="text/plain")
        try:
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            call_sid = (
                params.get("CallSid")
                or params.get("callSid")
                or params.get("DialCallSid")
            )
            call_status = (
                params.get("DialCallStatus")
                or params.get("CallStatus")
                or params.get("callStatus")
            )
            recording_sid = params.get("RecordingSid") or params.get("recordingSid")
            recording_status = params.get("RecordingStatus") or params.get("recordingStatus")
            duration_val = (
                params.get("DialCallDuration")
                or params.get("Duration")
                or params.get("duration")
            )

            _logger.info(
                "Twilio event received: CallSid=%s CallStatus=%s RecordingSid=%s RecordingStatus=%s Duration=%s",
                call_sid, call_status, recording_sid, recording_status, duration_val
            )

            if call_sid and call_status:
                # Normalize Twilio status to model statuses
                normalized = (call_status or "").lower().replace("-", "_")
                try:
                    request.env["twilio.call.log"].sudo().update_call_status(call_sid, normalized)
                    if duration_val:
                        try:
                            dur_int = int(duration_val)
                            if dur_int > 0:
                                log = request.env["twilio.call.log"].sudo().search([("call_sid", "=", call_sid)], limit=1)
                                if log:
                                    log.sudo().write({
                                        "duration": dur_int,
                                        "end_time": fields.Datetime.now(),
                                    })
                        except (ValueError, TypeError):
                            pass
                except Exception:
                    _logger.exception("Failed to update call status for CallSid=%s", call_sid)

            if call_sid and recording_sid:
                try:
                    dial_call_sid = params.get("DialCallSid") or params.get("dialCallSid") or ""
                    log = request.env["twilio.call.log"].sudo().search([
                        "|", ("call_sid", "=", call_sid), ("call_sid", "=", dial_call_sid)
                    ], limit=1)
                    if not log:
                        # Try finding log by parent_call_sid from Twilio
                        try:
                            client = request.env["twilio.service"].get_twilio_client()
                            call_obj = client.calls(call_sid).fetch()
                            parent_sid = getattr(call_obj, "parent_call_sid", None)
                            if parent_sid:
                                log = request.env["twilio.call.log"].sudo().search([("call_sid", "=", parent_sid)], limit=1)
                        except Exception:
                            pass
                    if log:
                        request.env.cr.execute("SELECT id FROM twilio_call_log WHERE id = %s FOR UPDATE", (log.id,))
                        log.invalidate_recordset(["recording_status", "recording_url"])
                        if not (log.recording_status == "completed" and log.recording_url):
                            account_sid = request.env["ir.config_parameter"].sudo().get_param("twilio_dialer.account_sid")
                            url = log._build_recording_url(account_sid, recording_sid)
                            status_map = {"completed": "completed", "in-progress": "recording", "processing": "pending", "failed": "failed"}
                            mapped_status = status_map.get((recording_status or "").lower(), "completed")
                            vals = {
                                "recording_sid": recording_sid,
                                "recording_url": url,
                                "recording_status": mapped_status,
                            }
                            log.write(vals)
                            log._post_recording_to_chatter()
                            icp = request.env["ir.config_parameter"].sudo()
                            if icp.get_param("twilio_dialer.ai_enable_transcript") in ("True", "true", "1"):
                                log._sync_transcript_from_twilio()
                except Exception:
                    _logger.exception("Failed to record recording callback for CallSid=%s RecordingSid=%s", call_sid, recording_sid)

            return request.make_response("", headers={"Content-Type": "text/plain"})
        except Exception:
            _logger.exception("Unhandled error in twilio_event")
            return request.make_response("", status=500)

    @http.route("/twilio_dialer/sms/get_history", type="json", auth="user")
    def get_sms_history(self, phone=None, limit=30, page_token=None, **kwargs):
        """Fetch live SMS conversation history for a given phone number directly via TwilioService.

        Supports lazy loading with page_token and limit (default 30).
        SMS messages are NOT read from or stored in the Odoo database.
        """
        if not phone:
            return {"success": False, "message": "Phone number is required.", "messages": [], "has_more": False}

        try:
            service = request.env["twilio.service"]
            client = service.get_twilio_client()

            # Limit default to 30 for lazy loading performance
            fetch_limit = int(limit or 30)

            # Retrieve messages To and From recipient
            messages_to = client.messages.list(to=phone, limit=fetch_limit)
            messages_from = client.messages.list(from_=phone, limit=fetch_limit)

            all_messages = messages_to + messages_from
            # Sort chronologically
            all_messages.sort(key=lambda m: m.date_created or m.date_sent)

            # Apply page offset windowing for lazy scrolling
            total_msgs = len(all_messages)
            has_more = total_msgs > fetch_limit

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

            return {
                "success": True,
                "messages": conversation,
                "has_more": has_more,
            }
        except Exception as e:
            _logger.error("Failed to fetch SMS history for %s: %s", phone, str(e))
            return {"success": False, "message": str(e), "messages": [], "has_more": False}

    @http.route("/twilio_dialer/sms/get_templates", type="json", auth="user")
    def get_sms_templates(self, partner_id=None, **kwargs):
        """Return active SMS templates with category information and rendered placeholder previews."""
        try:
            templates = request.env["twilio.sms.template"].search([("active", "=", True)])
            partner = None
            if partner_id:
                partner = request.env["res.partner"].browse(partner_id).exists()

            result = []
            for t in templates:
                rendered = t.render_template(partner=partner, user=request.env.user)
                result.append({
                    "id": t.id,
                    "name": t.name,
                    "category": t.category_id.name if t.category_id else "General",
                    "body": t.body or "",
                    "rendered_body": rendered,
                    "description": t.description or "",
                })
            return {"success": True, "templates": result}
        except Exception as e:
            _logger.error("Failed to fetch SMS templates: %s", str(e))
            return {"success": False, "message": str(e), "templates": []}

    @http.route("/twilio_dialer/sms/get_quick_replies", type="json", auth="user")
    def get_quick_replies(self, **kwargs):
        """Return active SMS quick replies from database configuration."""
        try:
            replies = request.env["twilio.sms.quick.reply"].search([("active", "=", True)])
            result = [{"id": r.id, "name": r.name, "body": r.body} for r in replies]
            return {"success": True, "quick_replies": result}
        except Exception as e:
            _logger.error("Failed to fetch quick replies: %s", str(e))
            return {"success": False, "message": str(e), "quick_replies": []}

    @http.route("/twilio_dialer/sms/send", type="json", auth="user")
    def send_sms(self, recipient=None, body=None, partner_id=None, **kwargs):
        """Send an SMS using centralized TwilioService and log rich Chatter entry."""
        if not recipient or not body:
            return {"success": False, "message": "Recipient phone number and message body are required."}

        try:
            service = request.env["twilio.service"]
            res = service.send_sms_message(recipient=recipient, body=body, partner_id=partner_id)
            return res
        except Exception as e:
            _logger.error("Failed to send SMS to %s: %s", recipient, str(e))
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/get_recent_logs", type="json", auth="user")
    def get_recent_logs(self, limit=20, **kwargs):
        """Return recent SMS logs for the embedded SMS Workspace logs table."""
        try:
            logs = request.env["twilio.sms.log"].search_read(domain=[], limit=limit)
            return {"success": True, "logs": logs}
        except Exception as e:
            _logger.error("Failed to fetch recent SMS logs: %s", str(e))
            return {"success": False, "message": str(e), "logs": []}

    @http.route("/twilio_dialer/sms/workspace_counts", type="json", auth="user")
    def get_workspace_counts(self, **kwargs):
        """Return counts for SMS Workspace dashboard cards."""
        try:
            env = request.env
            counts = {
                "contacts": env["res.partner"].search_count([("phone", "!=", False)]),
                "logs": env["twilio.sms.log"].search_count([]),
                "templates": env["twilio.sms.template"].search_count([("active", "=", True)]),
                "quick_replies": env["twilio.sms.quick.reply"].search_count([("active", "=", True)]),
            }
            return {"success": True, "counts": counts}
        except Exception as e:
            _logger.error("Failed to fetch SMS workspace counts: %s", str(e))
            return {"success": False, "message": str(e), "counts": {"contacts": 0, "logs": 0, "templates": 0, "quick_replies": 0}}

    @http.route("/twilio_dialer/sms/get_contacts", type="json", auth="user")
    def get_sms_contacts(self, **kwargs):
        """Return contacts with phone numbers for the WhatsApp-style messaging dialog."""
        try:
            partners = request.env["res.partner"].search([
                ("phone", "!=", False)
            ], order="name asc", limit=300)

            result = []
            for p in partners:
                phone = (p.phone or "").strip()
                if not phone:
                    continue
                company = p.company_id.name if p.company_id else (p.parent_id.name if p.parent_id else "")
                result.append({
                    "id": p.id,
                    "name": p.name or "Contact",
                    "phone": phone,
                    "company": company,
                })
            return {"success": True, "contacts": result}
        except Exception as e:
            _logger.error("Failed to fetch SMS contacts: %s", str(e))
            return {"success": False, "message": str(e), "contacts": []}


    @http.route("/twilio_dialer/call_log/create", type="json", auth="user")
    def create_call_log(self, call_sid=None, to_number=None, from_number=None, partner_id=None, direction="outgoing", res_model=None, res_id=None, lead_id=None, **kwargs):
        try:
            if not call_sid or not to_number:
                return {"success": False, "message": "call_sid and to_number required"}

            existing = request.env["twilio.call.log"].sudo().search([("call_sid", "=", call_sid)], limit=1)
            if existing:
                return {"success": True, "id": existing.id}

            icp = request.env["ir.config_parameter"].sudo()
            from_num = from_number or icp.get_param("twilio_dialer.phone_number") or ""

            target_lead_id = lead_id or False
            if not target_lead_id and res_model == "crm.lead" and res_id:
                target_lead_id = res_id

            target_partner_id = partner_id or False
            if not target_partner_id and res_model == "res.partner" and res_id:
                target_partner_id = res_id
            elif not target_partner_id and target_lead_id and "crm.lead" in request.env:
                lead = request.env["crm.lead"].sudo().browse(target_lead_id)
                if lead.exists() and lead.partner_id:
                    target_partner_id = lead.partner_id.id

            log = request.env["twilio.call.log"].sudo().create({
                "call_sid": call_sid,
                "to_number": to_number,
                "from_number": from_num,
                "partner_id": target_partner_id,
                "lead_id": target_lead_id,
                "res_model": res_model or False,
                "res_id": res_id or False,
                "direction": direction or "outgoing",
                "status": "ringing" if direction == "incoming" else "in_progress",
            })
            return {"success": True, "id": log.id}
        except Exception as e:
            _logger.error("Failed to create call log via RPC: %s", str(e))
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/call_log/update", type="json", auth="user")
    def update_call_log(self, call_sid=None, status=None, **kwargs):
        try:
            if not call_sid or not status:
                return {"success": False, "message": "call_sid and status required"}

            log = request.env["twilio.call.log"].sudo().search([("call_sid", "=", call_sid)], limit=1)
            if log:
                log.update_call_status(call_sid, status)
            return {"success": True}
        except Exception as e:
            _logger.error("Failed to update call log via RPC: %s", str(e))
            return {"success": False, "message": str(e)}

