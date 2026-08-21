import logging

import requests

_logger = logging.getLogger(__name__)


class MyBroadcastAPIError(Exception):
    """A user-safe error returned by the MyBroadcast API client."""


class MyBroadcastAPI:
    _base_url = "https://extension.mybroadcast.online"
    _timeout = 10

    def _request(self, method, path, **kwargs):
        try:
            response = requests.request(
                method,
                f"{self._base_url}{path}",
                timeout=self._timeout,
                **kwargs,
            )
            payload = response.json()
        except requests.Timeout as error:
            raise MyBroadcastAPIError("Call settings request timed out. Please try again.") from error
        except requests.RequestException as error:
            _logger.warning("MyBroadcast call settings request failed: %s", error)
            raise MyBroadcastAPIError("Call settings service is unavailable. Please try again later.") from error
        except ValueError as error:
            raise MyBroadcastAPIError("Call settings service returned an invalid response.") from error

        if not isinstance(payload, dict):
            _logger.warning("MyBroadcast returned a non-object Call Settings response: %r", payload)
            raise MyBroadcastAPIError("Call settings service returned an invalid response.")
        if not response.ok:
            message = payload.get("message") or payload.get("error") or "The request was rejected."
            raise MyBroadcastAPIError(message)
        if payload.get("success") is False:
            raise MyBroadcastAPIError(payload.get("message") or payload.get("error") or "Request was rejected.")
        return payload

    def send_otp(self, email, account_sid, first_name="User", purpose="registration"):
        """Send OTP verification email via MyBroadcast API."""
        return self._request(
            "POST",
            "/auth/otp/send",
            json={
                "email": email,
                "accountSid": account_sid,
                "firstName": first_name or "User",
                "purpose": purpose or "registration",
            },
        )

    def verify_otp(self, email, account_sid, otp):
        """Verify 6-digit OTP code via MyBroadcast API."""
        return self._request(
            "POST",
            "/auth/otp/verify",
            json={
                "email": email,
                "accountSid": account_sid,
                "otp": otp,
            },
        )

    def get_call_settings(self, account_sid):
        return self._request("GET", "/get-call-settings", params={"accountSid": account_sid})

    def save_call_settings(self, account_sid, settings):
        return self._request(
            "POST",
            "/call-settings",
            json={"accountSid": account_sid, **settings},
        )

    def get_billing(self, account_sid):
        return self._request("GET", "/billing/%s" % account_sid)

    def get_module_version(self, module_name="twilio_dialer"):
        """Fetch published module version + feature list for update notifications."""
        return self._request("GET", "/odoo/%s/version.json" % module_name)

