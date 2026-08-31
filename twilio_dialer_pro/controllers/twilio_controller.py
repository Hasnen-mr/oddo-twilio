# -*- coding: utf-8 -*-
import json
import logging
import re
from html import escape
from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

try:
    from twilio.twiml.voice_response import VoiceResponse, Dial
    _TWILIO_TWIML_AVAILABLE = True
except ImportError:
    _TWILIO_TWIML_AVAILABLE = False

_logger = logging.getLogger(__name__)


class TwilioController(http.Controller):

    def _validate_twilio_request(self):
        """Validate incoming Twilio webhook signatures."""
        icp = request.env["ir.config_parameter"].sudo()
        if not icp.get_param("twilio_dialer.validate_webhook"):
            return True
        auth_token = icp.get_param("twilio_dialer.auth_token")
        if not auth_token:
            return True
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(auth_token)
        signature = request.httprequest.headers.get("X-Twilio-Signature", "")
        url = request.httprequest.url
        post_vars = request.httprequest.form.to_dict()
        return validator.validate(url, post_vars, signature)

    @http.route(
        ["/twilio_dialer/token", "/twilio_dialer/token/<string:subpath>"],
        type="http",
        auth="user",
        methods=["GET", "POST"],
        csrf=False,
    )
    def get_token(self, **kwargs):
        try:
            force_refresh = (
                kwargs.get("refresh") in ("1", "true", "True")
                or kwargs.get("force_refresh") in ("1", "true", "True", True)
                or request.httprequest.args.get("refresh") in ("1", "true", "True")
            )
            token = request.env["twilio.service"].generate_access_token(
                request.env,
                force_refresh=force_refresh,
            )
            allowed_numbers = []
            allocation_model = request.env.get("twilio.number.allocation")
            if allocation_model is not None:
                try:
                    user_id = request.env.user.id if request.env.user else False
                    allowed_numbers = allocation_model.sudo().get_user_allowed_numbers(user_id)
                except Exception as e:
                    _logger.debug("Token allocation retrieval fallback: %s", e)

            return request.make_response(
                json.dumps({
                    "success": True,
                    "token": token,
                    "allowed_numbers": allowed_numbers,
                }),
                headers=[("Content-Type", "application/json; charset=utf-8")],
            )
        except Exception as e:
            _logger.error("Failed to generate Twilio access token: %s", str(e))
            return request.make_response(
                json.dumps({"success": False, "message": str(e), "token": False, "allowed_numbers": []}),
                headers=[("Content-Type", "application/json; charset=utf-8")],
            )

    @http.route("/twilio_dialer/billing", type="json", auth="user")
    def get_billing_info(self):
        try:
            service = request.env["twilio.service"]
            billing_info = service.get_billing_info()
            return {"billing_info": billing_info}
        except Exception as e:
            _logger.error("Failed to get Twilio billing info: %s", str(e))
    @http.route("/twilio_dialer/call_info", type="json", auth="user")
    def get_call_info(self, call_sid=None):
        if not call_sid:
            return {"success": False, "to_number": ""}
        try:
            service = request.env["twilio.service"]
            client = service.get_twilio_client()
            call_obj = client.calls(call_sid).fetch()
            to_number = getattr(call_obj, "to_formatted", None) or getattr(call_obj, "to", None) or ""
            if to_number.startswith("client:") or to_number.startswith("id_odoo_") or to_number.startswith("id_"):
                parent_sid = getattr(call_obj, "parent_call_sid", None)
                if parent_sid:
                    parent_call = client.calls(parent_sid).fetch()
                    to_number = getattr(parent_call, "to_formatted", None) or getattr(parent_call, "to", None) or ""
            return {
                "success": True,
                "to_number": to_number,
                "from_number": getattr(call_obj, "from_formatted", None) or getattr(call_obj, "_from", None) or "",
                "call_sid": call_sid,
            }
        except Exception as e:
            _logger.warning("Failed to fetch call info for %s: %s", call_sid, e)
            return {"success": False, "to_number": ""}

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

            # Filter allowed phone numbers by user allocation
            allocation_model = request.env.get("twilio.number.allocation")
            if allocation_model is not None:
                try:
                    user_id = request.env.user.id if request.env.user else False
                    allowed_numbers = allocation_model.sudo().get_user_allowed_numbers(user_id)
                    if allowed_numbers:
                        phone_number = allowed_numbers[0]["phone_number"]
                        return {
                            "phone_number": phone_number,
                            "phone_numbers": allowed_numbers,
                        }
                except Exception as e:
                    _logger.debug("Number allocation retrieval fallback: %s", e)

            # Fallback if no allocation model: fetch incoming phone numbers and outgoing caller IDs live
            raw_incoming = service.get_incoming_phone_numbers() or []
            callers = []
            seen = set()
            
            for item in raw_incoming:
                p_num = item.get("phone_number")
                f_name = item.get("friendly_name") or p_num
                if p_num and p_num not in seen:
                    seen.add(p_num)
                    callers.append({
                        "phone_number": p_num,
                        "friendly_name": f_name,
                        "display_name": f"{f_name} ({p_num})",
                        "type": "incoming",
                    })

            try:
                for caller_id in (service.get_outgoing_caller_ids() or []):
                    p_num = caller_id.get("phone_number")
                    f_name = caller_id.get("friendly_name") or p_num
                    if p_num and p_num not in seen:
                        seen.add(p_num)
                        callers.append({
                            "phone_number": p_num,
                            "friendly_name": f_name,
                            "display_name": f"{f_name} ({p_num})",
                            "type": "outgoing_caller_id",
                        })
            except Exception as e:
                _logger.debug("Twilio outgoing caller IDs notice: %s", e)

            phone_number = callers[0]["phone_number"] if callers else (icp.get_param("twilio_dialer.phone_number") or False)

            return {
                "phone_number": phone_number,
                "phone_numbers": callers,
            }
        except Exception as e:
            _logger.error("Failed to get Twilio phone number: %s", str(e))
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

            # An outbound call from Odoo browser softphone always has a client identity (e.g. client:id_odoo_...)
            is_outbound_softphone = (
                str(caller_param).strip().lower().startswith("client:")
                or str(caller_param).strip().lower().startswith("id_odoo_")
                or bool(params.get("destination"))
                or bool(params.get("phone"))
            )

            # If it's an inbound call from an outside phone, route to incoming_call handler
            if direction.startswith("inbound") or not is_outbound_softphone:
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
        """Handle Twilio incoming call webhook and return TwiML."""
        if not self._validate_twilio_request():
            return Response("Forbidden: Invalid Twilio Signature", status=403, content_type="text/plain")
        try:
            params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
            call_sid = params.get("CallSid") or params.get("callSid") or ""
            from_number = params.get("From") or params.get("from") or ""
            to_number = params.get("To") or params.get("to") or params.get("Called") or params.get("called") or ""

            _logger.info("Incoming call webhook received: CallSid=%s From=%s To=%s", call_sid, from_number, to_number)

            if call_sid:
                request.env["twilio.call.log"].sudo().create_incoming_call(call_sid, from_number, to_number)

            icp = request.env["ir.config_parameter"].sudo()
            account_sid = icp.get_param("twilio_dialer.account_sid") or ""
            incoming = {}
            if account_sid:
                try:
                    from ..services import MyBroadcastAPI
                    payload = MyBroadcastAPI().get_call_settings(account_sid)
                    settings_model = request.env["res.config.settings"].sudo()
                    incoming_vals, outgoing_vals, error = settings_model._parse_call_settings(payload)
                    if not error:
                        incoming = incoming_vals
                except Exception:
                    _logger.debug("MyBroadcast call settings check passed")

            enable_transcription = icp.get_param("twilio_dialer.incoming_transcription") in ("True", "true", "1")
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
            if not welcome_greeting:
                welcome_greeting = icp.get_param("twilio_dialer.incoming_welcome_greeting") in ("True", "true", "1")
            if not welcome_greeting_text:
                welcome_greeting_text = icp.get_param("twilio_dialer.incoming_welcome_greeting_text", "") or ""

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

            if forward and forward_to and isinstance(forward_to, str) and forward_to.strip() and any(ch.isdigit() for ch in forward_to):
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
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            if voicemail and not forward:
                say = escape(voicemail_text) if voicemail_text else "Please leave a message after the tone."
                greet_xml = f"<Say>{escape(greeting_say)}</Say>" if greeting_say else ""
                twiml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response>{greet}<Say>{say}</Say><Record maxLength="120" playBeep="true"/></Response>'
                ).format(greet=greet_xml, say=say)
                return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})

            # Direct unified WebRTC client identity matching:
            client_identity = f"id_odoo_{account_sid}" if account_sid else "agent"
            caller_id_val = from_number or icp.get_param("twilio_dialer.phone_number") or ""

            if _TWILIO_TWIML_AVAILABLE:
                from twilio.twiml.voice_response import Client
                response = VoiceResponse()
                if greeting_say:
                    response.say(greeting_say)
                dial = Dial(
                    caller_id=caller_id_val,
                    answer_on_bridge=True,
                    action="/twilio_dialer/twilio_event",
                    record="record-from-answer-dual" if record_call else None,
                )
                client = Client(client_identity)
                if to_number:
                    client.parameter(name="To", value=to_number)
                    client.parameter(name="CalledNumber", value=to_number)
                dial.append(client)
                response.append(dial)
                twiml = str(response)
            else:
                record_attr = ' record="record-from-answer-dual"' if record_call else ""
                say_xml = f"<Say>{escape(greeting_say)}</Say>" if greeting_say else ""
                param_xml = f'<Parameter name="To" value="{escape(to_number)}"/><Parameter name="CalledNumber" value="{escape(to_number)}"/>' if to_number else ""
                twiml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response>'
                    '{say}'
                    '<Dial callerId="{caller_id}" answerOnBridge="true" action="/twilio_dialer/twilio_event"{record}>'
                    '<Client>{client}{params}</Client>'
                    '</Dial>'
                    '</Response>'
                ).format(
                    say=say_xml,
                    caller_id=escape(caller_id_val),
                    record=record_attr,
                    client=escape(client_identity),
                    params=param_xml,
                )

            _logger.info("[Twilio Incoming] TwiML generated for client %s: %s", client_identity, twiml)
            return request.make_response(twiml, headers={"Content-Type": "text/xml; charset=utf-8"})
        except Exception as e:
            _logger.error("Incoming call webhook error: %s", str(e), exc_info=True)
            twiml_err = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred handling your incoming call.</Say><Hangup/></Response>'
            return request.make_response(twiml_err, headers={"Content-Type": "text/xml; charset=utf-8"})

    @http.route(
        "/twilio_dialer/twilio_event",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def twilio_event(self, **kwargs):
        params = kwargs or dict(request.httprequest.form) or dict(request.httprequest.args)
        call_sid = params.get("CallSid") or params.get("callSid") or ""
        call_status = params.get("CallStatus") or params.get("DialCallStatus") or ""
        duration = params.get("CallDuration") or params.get("DialCallDuration") or 0

        _logger.info("Twilio Event: CallSid=%s Status=%s Duration=%s", call_sid, call_status, duration)

        if call_sid:
            log = request.env["twilio.call.log"].sudo().search([("call_sid", "=", call_sid)], limit=1)
            if log:
                vals = {}
                if call_status:
                    vals["status"] = call_status
                if duration:
                    vals["duration"] = int(duration)
                if vals:
                    log.write(vals)

        response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        return request.make_response(response, headers={"Content-Type": "text/xml; charset=utf-8"})

    @http.route("/twilio_dialer/sms/get_contacts", type="json", auth="user")
    def get_sms_contacts(self, **kwargs):
        try:
            domain = [("phone", "!=", False)]
            contacts = request.env["res.partner"].sudo().search_read(
                domain,
                ["id", "name", "phone", "email", "image_128"],
                limit=100,
            )
            return {"success": True, "contacts": contacts}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/get_templates", type="json", auth="user")
    def get_sms_templates(self, **kwargs):
        try:
            templates = request.env["twilio.sms.template"].sudo().search_read(
                [],
                ["id", "name", "body", "category"],
            )
            return {"success": True, "templates": templates}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/get_quick_replies", type="json", auth="user")
    def get_sms_quick_replies(self, **kwargs):
        try:
            replies = request.env["twilio.sms.quick.reply"].sudo().search_read(
                [],
                ["id", "label", "text"],
            )
            return {"success": True, "quick_replies": replies}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/get_history", type="json", auth="user")
    def get_sms_history(self, **kwargs):
        try:
            partner_id = kwargs.get("partner_id")
            phone = kwargs.get("phone")
            domain = []
            if partner_id:
                domain.append(("partner_id", "=", partner_id))
            elif phone:
                domain.append("|")
                domain.append(("to_number", "ilike", phone))
                domain.append(("from_number", "ilike", phone))
            logs = request.env["twilio.sms.log"].sudo().search_read(
                domain,
                ["id", "direction", "body", "status", "create_date", "to_number", "from_number"],
                order="create_date desc",
                limit=50,
            )
            return {"success": True, "messages": logs}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/workspace_counts", type="json", auth="user")
    def get_sms_workspace_counts(self, **kwargs):
        try:
            contacts = request.env["res.partner"].sudo().search_count([
                "|", ("phone", "!=", False), ("mobile", "!=", False)
            ])
            logs = request.env["twilio.sms.log"].sudo().search_count([])
            templates = request.env["twilio.sms.template"].sudo().search_count([]) if "twilio.sms.template" in request.env else 0
            quick_replies = request.env["twilio.quick.reply"].sudo().search_count([]) if "twilio.quick.reply" in request.env else 0
            sent = request.env["twilio.sms.log"].sudo().search_count([("direction", "=", "outgoing")])
            received = request.env["twilio.sms.log"].sudo().search_count([("direction", "=", "incoming")])
            counts = {
                "contacts": contacts,
                "logs": logs,
                "templates": templates,
                "quick_replies": quick_replies,
                "sent": sent,
                "received": received,
                "total": logs,
            }
            return {"success": True, "counts": counts, "total": logs, "sent": sent, "received": received}
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "counts": {"contacts": 0, "logs": 0, "templates": 0, "quick_replies": 0, "sent": 0, "received": 0, "total": 0}
            }

    @http.route("/twilio_dialer/sms/get_recent_logs", type="json", auth="user")
    def get_sms_recent_logs(self, **kwargs):
        try:
            limit = kwargs.get("limit", 50)
            logs = request.env["twilio.sms.log"].sudo().search_read(
                [],
                ["id", "direction", "to_number", "from_number", "body", "status", "create_date", "partner_id"],
                order="create_date desc",
                limit=limit,
            )
            return {"success": True, "logs": logs}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/sms/send", type="json", auth="user")
    def send_sms_json(self, **kwargs):
        to_number = kwargs.get("to_number")
        body = kwargs.get("body")
        from_number = kwargs.get("from_number")
        partner_id = kwargs.get("partner_id")
        lead_id = kwargs.get("lead_id")

        if not to_number or not body:
            return {"success": False, "message": "Missing to_number or body"}

        try:
            service = request.env["twilio.service"]
            sms = service.send_sms(
                to_number=to_number,
                body=body,
                from_number=from_number,
                partner_id=partner_id,
                lead_id=lead_id,
            )
            return {"success": True, "sms_id": sms.id}
        except Exception as e:
            _logger.error("Failed to send SMS: %s", str(e))
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/call_log/create", type="json", auth="user")
    def create_call_log(self, **kwargs):
        try:
            log = request.env["twilio.call.log"].sudo().create_call_log(**kwargs)
            return {"success": True, "call_log_id": log.id if log else False}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/call_log/update", type="json", auth="user")
    def update_call_log(self, **kwargs):
        try:
            request.env["twilio.call.log"].sudo().update_call_log(**kwargs)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/auto_dialer/sync_line", type="json", auth="user")
    def auto_dialer_sync_line(self, **kwargs):
        try:
            line_id = kwargs.get("queue_line_id")
            status = kwargs.get("status")
            notes = kwargs.get("notes")
            duration = kwargs.get("duration")
            if line_id:
                line = request.env["twilio.auto.dialer.line"].sudo().browse(line_id)
                if line.exists():
                    vals = {}
                    if status:
                        vals["status"] = status
                    if notes is not None:
                        vals["notes"] = notes
                    if duration:
                        vals["duration"] = duration
                    line.write(vals)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @http.route("/twilio_dialer/auto_dialer/navigate", type="json", auth="user")
    def auto_dialer_navigate(self, **kwargs):
        try:
            auto_dialer_id = kwargs.get("auto_dialer_id")
            current_line_id = kwargs.get("current_line_id")
            direction = kwargs.get("direction", "next")
            ad = request.env["twilio.auto.dialer"].sudo().browse(auto_dialer_id)
            if not ad.exists():
                return {"success": False, "message": "Auto dialer campaign not found"}
            res = ad.get_navigation_line(current_line_id, direction)
            return {"success": True, **res}
        except Exception as e:
            return {"success": False, "message": str(e)}
