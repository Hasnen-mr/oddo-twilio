import json
import logging

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class TwilioController(http.Controller):

    @http.route("/twilio_dialer/token", type="http", auth="user", methods=["GET"])
    def get_token(self, **kwargs):
        """Return a Voice Access Token."""
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
            _logger.info("Twilio access token unconfigured or unavailable: %s", str(e))
            return request.make_json_response(
                {"success": False, "configured": False, "message": str(e)}, status=200
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
