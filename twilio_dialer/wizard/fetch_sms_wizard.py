# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

from odoo import fields, models
from datetime import datetime

class TwilioSmsLine(models.TransientModel):
    _name = "twilio.sms.line"
    _description = "Twilio SMS (fetched)"

    from_number = fields.Char("From")
    to_number = fields.Char("To")
    body = fields.Text("Body")
    date_created = fields.Datetime("Date")
    status = fields.Char("Status")
    sid = fields.Char("SID")


class FetchSmsWizard(models.TransientModel):
    _name = "twilio.fetch.sms.wizard"
    _description = "Fetch SMS History from Twilio"

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
        line_model = self.env["twilio.sms.line"]
        line_model.search([]).unlink()
        try:
            path = "/2010-04-01/Accounts/%s/Messages.json?PageSize=20" % config.account_sid
            while path:
                data = config._twilio_request(path)
                # for m in data.get("messages", []):
                #     line_model.create({
                #         "from_number": m.get("from"),
                #         "to_number": m.get("to"),
                #         "body": m.get("body"),
                #         "date_created": m.get("date_created"),
                #         "status": m.get("status"),
                #         "sid": m.get("sid"),
                #     })
                for m in data.get("messages", []):

                    date_str = m.get("date_created")
                    date_val = False

                    if date_str:
                        try:
                           date_val = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                        except:
                             date_val = False
 
                    line_model.create({
                        "from_number": m.get("from"),
                        "to_number": m.get("to"),
                        "body": m.get("body"),
                        "date_created": date_val,
                        "status": m.get("status"),
                        "sid": m.get("sid"),
                   })
                path = data.get("next_page_uri")
            return {
                "type": "ir.actions.act_window",
                "name": "SMS History",
                "res_model": "twilio.sms.line",
                "view_mode": "list",
                "target": "current",
                "context": {"create": False, "delete": False},
            }
        except ValueError as e:
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
