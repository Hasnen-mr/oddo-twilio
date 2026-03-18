# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

import base64
import json
import urllib.request
from datetime import datetime
from odoo import api, fields, models


class TwilioCallLine(models.TransientModel):
    _name = "twilio.call.line"
    _description = "Twilio Call log (fetched)"

    from_number = fields.Char("From")
    to_number = fields.Char("To")
    direction = fields.Char("Direction")
    status = fields.Char("Status")
    duration = fields.Integer("Duration (s)")
    date_created = fields.Datetime("Date")
    sid = fields.Char("SID")
    recording_url = fields.Char("Recording URL", readonly=True)

    

    recording_player = fields.Html(
    string="Recording Player",
    compute="_compute_recording_player",
    sanitize=False
)
    def _compute_recording_player(self):
        for rec in self:
            if rec.recording_url:
               rec.recording_player = f"""
                   <a href="{rec.recording_url}" target="_blank" style="font-size:18px;">
                    ▶
                   </a>
               """
            else:
                rec.recording_player = ""
    
    

    @api.model
    def action_open_call_logs(self):
        """Open call logs list view and fetch from Twilio if empty.

        This reuses the existing fetch wizard logic but avoids showing
        the popup wizard to the user.
        """
        line_model = self.env["twilio.call.line"]
        if not line_model.search_count([]):
            # No logs yet: fetch them using the existing wizard logic.
            wizard = self.env["twilio.fetch.calls.wizard"].create({})
            action = wizard.action_fetch()
            # The wizard already returns either a window action to open
            # the list view or a client notification; just propagate it.
            if isinstance(action, dict):
                return action

        # Logs already exist (or fetch returned no explicit action):
        # open the list view directly.
        return {
            "type": "ir.actions.act_window",
            "name": "Call Logs",
            "res_model": "twilio.call.line",
            "view_mode": "list",
            "target": "current",
            "context": {"create": False, "delete": False},
        }


class FetchCallsWizard(models.TransientModel):
    _name = "twilio.fetch.calls.wizard"
    _description = "Fetch Call Logs from Twilio"

    def action_fetch(self):
        config = self.env["twilio_config"].get_config()
        if not config.account_sid or not config.auth_token:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Configuration missing",
                    "message": "Set Twilio Account SID and Auth Token in Twilio Configuration.",
                    "type": "warning",
                    "sticky": True,
                },
            }
        
        line_model = self.env["twilio.call.line"]
        # Explicit refresh: clear existing fetched logs before reloading
        # line_model.search([]).unlink()
        try:
            # Use a larger page size to minimize API calls
            path = "/2010-04-01/Accounts/%s/Calls.json?PageSize=100" % config.account_sid
            credentials = base64.b64encode(
                (config.account_sid + ":" + config.auth_token).encode()
            ).decode()

            vals_list = []
            # Limit how many calls we fetch recordings for to avoid
            # a separate API call per call and keep the process fast.
            max_recordings_fetch = 50
            recordings_fetched = 0

            while path:
                url = path if path.startswith("http") else ("https://api.twilio.com" + path)
                req = urllib.request.Request(url, headers={"Authorization": "Basic " + credentials})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())

                for c in data.get("calls", []):
                    rec_url = None
                    call_sid = c.get("parent_call_sid") or c.get("sid")

                    # Optionally fetch a recording URL, but not for every call
                    if recordings_fetched < max_recordings_fetch:
                        try:
                            rec_path = "/2010-04-01/Accounts/%s/Recordings.json?CallSid=%s" % (
                                config.account_sid,
                                call_sid,
                            )
                            rec_data = config._twilio_request(rec_path)
                            if rec_data.get("recordings"):
                                rec = rec_data["recordings"][0]
                                rec_url = "https://api.twilio.com" + rec.get("uri", "").replace(".json", ".mp3")
                                recordings_fetched += 1
                        except Exception:
                            # If recording lookup fails, just skip it and continue
                            rec_url = None
                    

                    date_created = c.get("date_created")
                    parsed_date = False

                    if date_created:
                        try:
                            parsed_date = datetime.strptime(
                                date_created,
                                "%a, %d %b %Y %H:%M:%S %z",
                            ).replace(tzinfo=None)
                        except Exception:
                            parsed_date = False

                    vals_list.append(
                        {
                            "from_number": c.get("from"),
                            "to_number": c.get("to"),
                            "direction": c.get("direction"),
                            "status": c.get("status"),
                            "duration": int(c.get("duration") or 0),
                            "date_created": parsed_date,
                            "sid": c.get("sid"),
                            "recording_url": rec_url,
                        }
                    )

                path = data.get("next_page_uri")
                if path and not path.startswith("http"):
                    path = "https://api.twilio.com" + path

            if vals_list:
                # Bulk create for better ORM performance
                line_model.create(vals_list)
            return {
                "type": "ir.actions.act_window",
                "name": "Call Logs",
                "res_model": "twilio.call.line",
                "view_mode": "list",
                "target": "current",
                "context": {"create": False, "delete": False},
            }
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Fetch failed",
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
