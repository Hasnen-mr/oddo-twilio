# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

import base64
import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

from odoo import api, fields, models


class TwilioConfig(models.Model):
    _name = "twilio.config"
    _description = "Twilio Configuration"
    _rec_name = "account_sid"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    account_sid = fields.Char("Account SID", required=True, help="Twilio Account SID (starts with AC)")
    auth_token = fields.Char("Auth Token", required=True, password=True, help="Twilio Auth Token (secret)")
    default_from_number = fields.Char("Default From Number", help="Default Twilio number for SMS and calls")

    def _twilio_request(self, path, method="GET", data=None):
        """Perform HTTP request to Twilio API with Basic auth. path is e.g. /2010-04-01/Accounts/ACxxx.json"""
        self.ensure_one()
        url = "https://api.twilio.com" + path
        credentials = base64.b64encode(
            (self.account_sid + ":" + self.auth_token).encode()
        ).decode()
        headers = {"Authorization": "Basic " + credentials}
        if data and method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urlencode(data).encode()
        else:
            body = None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode()
                err_data = json.loads(err_body)
                raise ValueError(err_data.get("message", err_body))
            except (ValueError, json.JSONDecodeError):
                raise ValueError(str(e))
        except urllib.error.URLError as e:
            raise ValueError(str(e.reason))

    def action_test_connection(self):
        """Verify credentials by fetching account info."""
        self.ensure_one()
        try:
            self._twilio_request("/2010-04-01/Accounts/%s.json" % self.account_sid)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Connection successful",
                    "message": "Twilio credentials are valid.",
                    "type": "success",
                    "sticky": False,
                },
            }
        except ValueError as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Connection failed",
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }

    def get_phone_numbers(self):
        """Fetch IncomingPhoneNumbers from Twilio; returns list of dicts with sid, phone_number, friendly_name."""
        self.ensure_one()
        if not self.account_sid or not self.auth_token:
            return []
        try:
            data = self._twilio_request(
                "/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json?PageSize=100"
                % self.account_sid
            )
            return [
                {
                    "sid": r["sid"],
                    "phone_number": r.get("phone_number", ""),
                    "friendly_name": r.get("friendly_name", r.get("phone_number", "")),
                }
                for r in data.get("incoming_phone_numbers", [])
            ]
        except ValueError:
            return []

    @api.model
    def get_config(self):
        """Return config for current company, or empty recordset if none."""
        company = self.env.company
        return self.search([("company_id", "=", company.id)], limit=1)
