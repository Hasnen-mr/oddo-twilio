import logging
from urllib.parse import urlparse

from odoo import models
from odoo.exceptions import UserError

from ..services import MyBroadcastAPI, MyBroadcastAPIError

_logger = logging.getLogger(__name__)


class TwilioBillingService(models.AbstractModel):
    _name = "twilio.billing.service"
    _description = "Twilio Billing Service"

    @staticmethod
    def _number(payload, key):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            _logger.warning("MyBroadcast Billing returned invalid %s: %r", key, value)
            return None
        return value

    @staticmethod
    def _url(payload, key):
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            return False
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            _logger.warning("MyBroadcast Billing returned invalid %s URL: %r", key, value)
            return False
        return value

    def get_billing(self):
        account_sid = self.env["ir.config_parameter"].sudo().get_param("twilio_dialer.account_sid")
        payload = {}
        if account_sid:
            try:
                api_result = MyBroadcastAPI().get_billing(account_sid)
                if isinstance(api_result, dict):
                    payload = api_result
            except Exception as error:
                _logger.warning("MyBroadcast Billing API returned error or is unreachable: %s", error)

        incoming = self._number(payload, "incoming")
        outgoing = self._number(payload, "outgoing")
        if incoming is None:
            incoming = self.env["twilio.call.log"].sudo().search_count([("direction", "=", "inbound")]) if "twilio.call.log" in self.env else 0
        if outgoing is None:
            outgoing = self.env["twilio.call.log"].sudo().search_count([("direction", "=", "outbound")]) if "twilio.call.log" in self.env else 0
        usage = incoming + outgoing

        return {
            "accountSid": account_sid or False,
            "incoming": incoming,
            "outgoing": outgoing,
            "usage": usage,
            "limit": "Unlimited",
            "remaining": "Unlimited",
            "paymentDone": payload.get("payment_done") if isinstance(payload.get("payment_done"), bool) else True,
            "paymentDue": payload.get("payment_due") if isinstance(payload.get("payment_due"), bool) else False,
            "email": payload.get("email") if isinstance(payload.get("email"), str) else False,
            "lastCallAt": payload.get("lastCallAt") if isinstance(payload.get("lastCallAt"), str) else False,
            "billingUrl": self._url(payload, "link"),
            "topUpUrl": self._url(payload, "topuplink"),
        }
