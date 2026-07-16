import logging
from xml.sax.saxutils import escape

from odoo import http
from odoo.exceptions import UserError
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
            phone_number = request.env["twilio.service"].get_twilio_phone_number()
            return {"phone_number": phone_number}
        except UserError as e:
            return {"phone_number": False, "message": str(e)}

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
    def create_call_log(self, call_sid, to_number):
        call_log = request.env["twilio.call.log"].create_outgoing_call(
            call_sid,
            to_number,
        )
        return {"id": call_log.id}

    @http.route("/twilio_dialer/call_log/update", type="json", auth="user")
    def update_call_log(self, call_sid, status):
        request.env["twilio.call.log"].update_call_status(call_sid, status)
        return {"success": True}
