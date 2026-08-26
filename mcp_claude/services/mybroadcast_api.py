# -*- coding: utf-8 -*-
import logging
import requests

_logger = logging.getLogger(__name__)


class MyBroadcastAPIError(Exception):
    """A user-safe error returned by the MyBroadcast API client."""
    pass


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
            raise MyBroadcastAPIError("Verification request timed out. Please try again.") from error
        except requests.RequestException as error:
            _logger.warning("MyBroadcast API request failed: %s", error)
            raise MyBroadcastAPIError("Verification service is temporarily unavailable. Please try again later.") from error
        except ValueError as error:
            raise MyBroadcastAPIError("Verification service returned an invalid response.") from error

        if not isinstance(payload, dict):
            _logger.warning("MyBroadcast returned a non-object response: %r", payload)
            raise MyBroadcastAPIError("Verification service returned an invalid response.")
        if not response.ok:
            message = payload.get("message") or payload.get("error") or "The request was rejected."
            raise MyBroadcastAPIError(message)
        if payload.get("success") is False:
            raise MyBroadcastAPIError(payload.get("message") or payload.get("error") or "Request was rejected.")
        return payload

    def send_otp(self, email, account_sid="", first_name="User", purpose="registration"):
        """Send OTP verification email via MyBroadcast API."""
        payload = {
            "email": email,
            "firstName": first_name or "User",
            "purpose": purpose or "registration",
        }
        if account_sid:
            payload["accountSid"] = account_sid
        return self._request(
            "POST",
            "/auth/otp/send",
            json=payload,
        )

    def verify_otp(self, email, account_sid="", otp=""):
        """Verify 6-digit OTP code via MyBroadcast API."""
        payload = {
            "email": email,
            "otp": otp,
        }
        if account_sid:
            payload["accountSid"] = account_sid
        return self._request(
            "POST",
            "/auth/otp/verify",
            json=payload,
        )
