# -*- coding: utf-8 -*-
import logging
import requests

_logger = logging.getLogger(__name__)


class ZantaTechAPIError(Exception):
    """User-safe error from the ZantaTech feedback API."""


class ZantaTechAPI:
    """Client for ZantaTech extension feedback / registration endpoints."""

    _base_url = "https://young.zantatech.com"
    _timeout = 10

    def submit_feedback(self, payload):
        """
        POST /extension/feeback

        Expected payload keys: accountSid, email, phone, message, title
        Optional: useCase
        """
        try:
            response = requests.post(
                f"{self._base_url}/extension/feeback",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            try:
                body = response.json()
            except ValueError as error:
                raise ZantaTechAPIError(
                    "Feedback service returned an invalid response."
                ) from error
        except requests.Timeout as error:
            raise ZantaTechAPIError(
                "Feedback request timed out. Please try again."
            ) from error
        except requests.RequestException as error:
            _logger.warning("ZantaTech feedback request failed: %s", error)
            raise ZantaTechAPIError(
                "Feedback service is unavailable. Please try again later."
            ) from error

        if not isinstance(body, dict):
            raise ZantaTechAPIError("Feedback service returned an invalid response.")
        if not response.ok or body.get("success") is False:
            raise ZantaTechAPIError(
                body.get("message") or "Feedback service rejected the request."
            )
        return body
