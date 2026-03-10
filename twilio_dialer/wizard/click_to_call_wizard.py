# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

from urllib.parse import quote

from odoo import api, fields, models


class ClickToCallWizard(models.TransientModel):
    _name = "twilio.click.to.call.wizard"
    _description = "Click-to-call via Twilio"

    from_number = fields.Selection(selection="_selection_from_number", string="From (Twilio number)", required=True)
    to_number = fields.Char("To (contact number)", required=True, help="E.164 format, e.g. +1234567890")
    caller_phone = fields.Char(
        "Your phone (to ring first)",
        required=True,
        help="Your phone in E.164 format. Twilio will call this number first; when you answer, it will dial the contact.",
    )

    @api.model
    def _selection_from_number(self):
        config = self.env["twilio_config"].get_config()
        if not config:
            return []
        numbers = config.get_phone_numbers()
        return [(n["phone_number"], n["friendly_name"] or n["phone_number"]) for n in numbers]

    def action_initiate_call(self):
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
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        if not base_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Configuration error",
                    "message": "Odoo base URL (web.base.url) must be set so Twilio can fetch the dial TwiML.",
                    "type": "danger",
                    "sticky": True,
                },
            }
        twiml_url = base_url + "/twilio/dial?to=" + quote(self.to_number)
        try:
            config._twilio_request(
                "/2010-04-01/Accounts/%s/Calls.json" % config.account_sid,
                method="POST",
                data={
                    "To": self.caller_phone,
                    "From": self.from_number,
                    "Url": twiml_url,
                },
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Call initiated",
                    "message": "Your phone will ring shortly. Answer to be connected to %s." % self.to_number,
                    "type": "success",
                    "sticky": False,
                },
            }
        except ValueError as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Call failed",
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
