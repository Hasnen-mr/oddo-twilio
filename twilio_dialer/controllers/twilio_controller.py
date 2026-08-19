import json
import logging
from xml.sax.saxutils import escape

from odoo import http
from odoo.exceptions import UserError, AccessDenied
from odoo.http import request

try:
    from twilio.twiml.voice_response import VoiceResponse, Dial, Client, Say, Record, Reject, Hangup
    _TWILIO_TWIML_AVAILABLE = True
except ImportError:
    _TWILIO_TWIML_AVAILABLE = False

_logger = logging.getLogger(__name__)


class TwilioController(http.Controller):

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
            import re
            service = request.env["twilio.service"]
            icp = request.env["ir.config_parameter"].sudo()
            try:
                phone_numbers = json.loads(
                    icp.get_param("twilio_dialer.incoming_phone_numbers", "[]")
                )
            except (TypeError, json.JSONDecodeError):
                phone_numbers = []

            if not phone_numbers:
                phone_numbers = service.get_incoming_phone_numbers()

            for item in phone_numbers:
                if isinstance(item, dict) and not item.get("type"):
                    item["type"] = "incoming"

            seen = {
                item.get("phone_number")
                for item in phone_numbers
                if isinstance(item, dict) and item.get("phone_number")
            }
            for caller_id in service.get_outgoing_caller_ids():
                number = caller_id.get("phone_number")
                if not number or number in seen:
                    continue
                seen.add(number)
                phone_numbers.append(caller_id)

            all_db_numbers = request.env["twilio.phone.number"].sudo().search([("phone_number", "!=", "ALL")])
            for db_num in all_db_numbers:
                if db_num.phone_number and db_num.phone_number not in seen:
                    seen.add(db_num.phone_number)
                    phone_numbers.append({
                        "phone_number": db_num.phone_number,
                        "friendly_name": db_num.display_name or db_num.phone_number,
                        "type": "incoming"
                    })

            user = request.env.user
            if user:
                allowed = user.get_allowed_twilio_numbers()
                if allowed:
                    allowed_digits = {re.sub(r"\D", "", n) for n in allowed if n}
                    filtered = [
                        item for item in phone_numbers
                        if isinstance(item, dict) and re.sub(r"\D", "", str(item.get("phone_number") or "")) in allowed_digits
                    ]
                    phone_numbers = filtered

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

    @http.route(
        "/twilio_dialer/call_setup",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def call_setup(self, **kwargs):
        try:
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            direction = (
                params.get("Direction")
                or params.get("direction")
                or request.httprequest.args.get("Direction", "")
                or ""
            ).lower()

            raw_from = (
                params.get("From")
                or params.get("from")
                or params.get("CallerId")
                or request.httprequest.args.get("From", "")
                or ""
            )
            from_str = str(raw_from).strip().lower()

            is_client_call = from_str.startswith("client:") or bool(params.get("destination")) or bool(params.get("phone"))

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
            if not caller_id:
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
                # Fallback to direct digits extraction if to_raw is standard phone
                digits_to = re.sub(r"\D", "", str(to_raw or ""))
                if digits_to:
                    to_number = "+" + digits_to if not str(to_raw).startswith("+") else "+" + digits_to

            if not to_number:
                raise UserError("Missing destination number for Twilio outbound call.")

            if _TWILIO_TWIML_AVAILABLE:
                response = VoiceResponse()
                dial = Dial(caller_id=caller_id)
                dial.number(to_number)
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
                # Use the official twilio-python SDK — guaranteed schema-correct TwiML
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
                # Fallback: manual construction (plain text-content form — valid per Twilio docs)
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
    def create_call_log(self, call_sid=None, phone_number=None, direction="outgoing", status="in_progress", partner_id=None, **kwargs):
        """Create or update a Twilio call log entry from the WebRTC client."""
        try:
            CallLog = request.env["twilio.call.log"].sudo()
            existing = False
            if call_sid:
                existing = CallLog.search([("call_sid", "=", call_sid)], limit=1)
            
            if existing:
                vals = {}
                if status:
                    vals["status"] = status
                if phone_number and not existing.phone_number:
                    vals["phone_number"] = phone_number
                if partner_id:
                    vals["partner_id"] = partner_id
                if vals:
                    existing.write(vals)
                log_id = existing.id
            else:
                log = CallLog.create({
                    "call_sid": call_sid or f"client_{request.env.user.id}_{fields.Datetime.now().timestamp()}",
                    "phone_number": phone_number or "",
                    "direction": direction,
                    "status": status,
                    "user_id": request.env.user.id,
                    "partner_id": partner_id or False,
                })
                log_id = log.id

            return {"success": True, "call_log_id": log_id}
        except Exception as e:
            _logger.error("Failed to create call log: %s", str(e))
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/call_log/update", type="json", auth="user")
    def update_call_log(self, call_log_id=None, call_sid=None, duration=0, status=None, **kwargs):
        """Update duration, status, or recording for a Twilio call log entry."""
        try:
            CallLog = request.env["twilio.call.log"].sudo()
            log = False
            if call_log_id:
                log = CallLog.browse(call_log_id).exists()
            elif call_sid:
                log = CallLog.search([("call_sid", "=", call_sid)], limit=1)

            if log:
                vals = {}
                if duration:
                    vals["duration"] = duration
                if status:
                    vals["status"] = status
                if vals:
                    log.write(vals)
                return {"success": True, "call_log_id": log.id}
            return {"success": False, "message": "Call log not found."}
        except Exception as e:
            _logger.error("Failed to update call log: %s", str(e))
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/auto_dialer/sync_line", type="json", auth="user")
    def sync_auto_dialer_line(self, dialer_id, **kwargs):
        dialer = request.env["twilio.auto.dialer"].sudo().browse(dialer_id)
        if not dialer.exists():
            return {"success": False, "message": "Queue not found"}

        current_line = dialer.current_line_id
        if current_line:
            partner = current_line.partner_id
            all_lines = dialer.queue_line_ids
            line_idx = list(all_lines).index(current_line) + 1 if current_line in all_lines else 1
            return {
                "success": True,
                "queue_line_id": current_line.id,
                "phone": current_line.phone,
                "partner_id": partner.id if partner else False,
                "partner_name": partner.name if partner else current_line.phone,
                "queue_name": dialer.name,
                "queue_position": "Line %s of %s" % (line_idx, len(all_lines)),
                "queue_attempts": current_line.attempt_count,
                "queue_notes": current_line.notes or "",
                "queue_status": current_line.status,
                "queue_state": dialer.state,
            }
        return {
            "success": True,
            "queue_line_id": False,
            "queue_state": dialer.state,
        }

    @http.route("/twilio_dialer/auto_dialer/navigate", type="json", auth="user")
    def navigate_auto_dialer(self, dialer_id, action_name):
        dialer = request.env["twilio.auto.dialer"].sudo().browse(dialer_id)
        if not dialer.exists():
            return {"success": False, "message": "Queue not found"}

        if action_name == "skip":
            dialer.action_skip_contact()
        elif action_name == "next":
            dialer.action_next_contact()
        elif action_name == "prev":
            dialer.action_prev_contact()
        elif action_name == "current":
            pass
        else:
            return {"success": False, "message": "Invalid action"}

        current_line = dialer.current_line_id
        if current_line:
            partner = current_line.partner_id
            all_lines = dialer.queue_line_ids
            line_idx = list(all_lines).index(current_line) + 1 if current_line in all_lines else 1
            return {
                "success": True,
                "queue_line_id": current_line.id,
                "phone": current_line.phone,
                "partner_id": partner.id if partner else False,
                "partner_name": partner.name if partner else current_line.phone,
                "queue_name": dialer.name,
                "queue_position": "Line %s of %s" % (line_idx, len(all_lines)),
                "queue_attempts": current_line.attempt_count,
                "queue_notes": current_line.notes or "",
                "queue_status": current_line.status,
                "queue_state": dialer.state,
            }
        return {"success": True, "queue_line_id": False, "queue_state": dialer.state}

    @http.route("/twilio_dialer/billing", type="json", auth="user")
    def get_billing(self):
        try:
            return {"success": True, "billing": request.env["twilio.billing.service"].get_billing()}
        except Exception as error:
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

