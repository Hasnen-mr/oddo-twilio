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
            message = payload.get("message") or "The configured Twilio Account SID was rejected."
            raise MyBroadcastAPIError(message)
        if payload.get("success") is False:
            raise MyBroadcastAPIError(payload.get("message") or "Call settings service rejected the request.")
        return payload

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
