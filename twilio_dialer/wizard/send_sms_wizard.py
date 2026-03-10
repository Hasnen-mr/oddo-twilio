# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

from odoo import api, fields, models


class SendSmsWizard(models.TransientModel):
    _name = "twilio.send.sms.wizard"
    _description = "Send SMS via Twilio"

    from_number = fields.Selection(selection="_selection_from_number", string="From", required=True)
    to_number = fields.Char("To", required=True, help="E.164 format, e.g. +1234567890")
    body = fields.Text("Message", required=True)

    @api.model
    def _selection_from_number(self):
        config = self.env["twilio_config"].get_config()
        if not config:
            return []
        numbers = config.get_phone_numbers()
        return [(n["phone_number"], n["friendly_name"] or n["phone_number"]) for n in numbers]

    def action_send_sms(self):
        self.ensure_one()
        config = self.env["twilio_config"].get_config()
        if not config:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Configuration missing",
                    "message": "Set Twilio Account SID and Auth Token in Twilio → Configuration.",
                    "type": "warning",
                    "sticky": True,
                },
            }
        try:
            config._twilio_request(
                "/2010-04-01/Accounts/%s/Messages.json" % config.account_sid,
                method="POST",
                data={
                    "From": self.from_number,
                    "To": self.to_number,
                    "Body": self.body,
                },
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "SMS sent",
                    "message": "Message sent to %s." % self.to_number,
                    "type": "success",
                    "sticky": False,
                },
            }
        except ValueError as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Failed to send SMS",
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
