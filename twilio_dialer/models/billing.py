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
        if not account_sid:
            raise UserError("Configure a Twilio Account SID before opening Billing.")
        try:
            payload = MyBroadcastAPI().get_billing(account_sid)
        except MyBroadcastAPIError as error:
            raise UserError(str(error)) from error
        if not isinstance(payload, dict):
            _logger.warning("MyBroadcast Billing returned a non-object payload: %r", payload)
            raise UserError("Billing service returned an invalid response.")

        incoming = self._number(payload, "incoming")
        outgoing = self._number(payload, "outgoing")
        limit = self._number(payload, "limit")
        if None in (incoming, outgoing, limit):
            raise UserError("Billing service returned incomplete or invalid usage data.")
        usage = incoming + outgoing
        return {
            "accountSid": account_sid,
            "incoming": incoming,
            "outgoing": outgoing,
            "usage": usage,
            "limit": limit,
            "remaining": max(limit - usage, 0),
            "paymentDone": payload.get("payment_done") if isinstance(payload.get("payment_done"), bool) else False,
            "paymentDue": payload.get("payment_due") if isinstance(payload.get("payment_due"), bool) else False,
            "email": payload.get("email") if isinstance(payload.get("email"), str) else False,
            "lastCallAt": payload.get("lastCallAt") if isinstance(payload.get("lastCallAt"), str) else False,
            "billingUrl": self._url(payload, "link"),
            "topUpUrl": self._url(payload, "topuplink"),
        }
