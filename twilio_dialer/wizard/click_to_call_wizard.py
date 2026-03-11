from urllib.parse import quote
from odoo import api, fields, models

class ClickToCallWizard(models.TransientModel):
    _name = "twilio.click.to.call.wizard"
    _description = "Click-to-call via Twilio"

    from_number = fields.Selection(selection="_selection_from_number", string="From (Twilio number)", required=True)
    to_number = fields.Char("To (contact number)")
    caller_phone = fields.Char("Your phone", required=True)

    # -------------------------------------------------------------------------
    # Dialpad helpers
    # -------------------------------------------------------------------------
    def _reopen_wizard(self):
        """Return an action that reopens this wizard with the same record."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
            'context': self.env.context,
        }

    def press_1(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "1"
        return self._reopen_wizard()

    def press_2(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "2"
        return self._reopen_wizard()

    def press_3(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "3"
        return self._reopen_wizard()

    def press_4(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "4"
        return self._reopen_wizard()

    def press_5(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "5"
        return self._reopen_wizard()

    def press_6(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "6"
        return self._reopen_wizard()

    def press_7(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "7"
        return self._reopen_wizard()

    def press_8(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "8"
        return self._reopen_wizard()

    def press_9(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "9"
        return self._reopen_wizard()

    def press_0(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "0"
        return self._reopen_wizard()

    def press_star(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "*"
        return self._reopen_wizard()

    def press_hash(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "#"
        return self._reopen_wizard()

    # -------------------------------------------------------------------------
    # Twilio call initiation
    # -------------------------------------------------------------------------
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


# # Part of Odoo. See LICENSE file for full copyright and licensing details.
# # License: LGPL-3

# from urllib.parse import quote

# from odoo import api, fields, models


# class ClickToCallWizard(models.TransientModel):
#     _name = "twilio.click.to.call.wizard"
#     _description = "Click-to-call via Twilio"

#     from_number = fields.Selection(selection="_selection_from_number", string="From (Twilio number)", required=True)
#     to_number = fields.Char("To (contact number)", required=True, help="E.164 format, e.g. +1234567890")
#     caller_phone = fields.Char(
#         "Your phone (to ring first)",
#         required=True,
#         help="Your phone in E.164 format. Twilio will call this number first; when you answer, it will dial the contact.",
#     )
#     def press_1(self):
#         self.to_number = (self.to_number or '') + "1"

#     def press_2(self):
#         self.to_number = (self.to_number or '') + "2"

#     def press_3(self):
#         self.to_number = (self.to_number or '') + "3"

#     def press_4(self):
#         self.to_number = (self.to_number or '') + "4"

#     def press_5(self):
#         self.to_number = (self.to_number or '') + "5"

#     def press_6(self):
#         self.to_number = (self.to_number or '') + "6"

#     def press_7(self):
#         self.to_number = (self.to_number or '') + "7"

#     def press_8(self):
#         self.to_number = (self.to_number or '') + "8"

#     def press_9(self):
#         self.to_number = (self.to_number or '') + "9"

#     def press_0(self):
#         self.to_number = (self.to_number or '') + "0"

#     def press_star(self):
#         self.to_number = (self.to_number or '') + "*"

#     def press_hash(self):
#         self.to_number = (self.to_number or '') + "#"

#     # 👇 Existing Twilio call method
#     def action_initiate_call(self):
#         self.ensure_one()
#         config = self.env["twilio_config"].get_config()
#         if not config:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": "Configuration missing",
#                     "message": "Set Twilio Account SID and Auth Token in Twilio → Configuration.",
#                     "type": "warning",
#                     "sticky": True,
#                 },
#             }

#     @api.model
#     def _selection_from_number(self):
#         config = self.env["twilio_config"].get_config()
#         if not config:
#             return []
#         numbers = config.get_phone_numbers()
#         return [(n["phone_number"], n["friendly_name"] or n["phone_number"]) for n in numbers]

#     def action_initiate_call(self):
#         self.ensure_one()
#         config = self.env["twilio_config"].get_config()
#         if not config:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": "Configuration missing",
#                     "message": "Set Twilio Account SID and Auth Token in Twilio → Configuration.",
#                     "type": "warning",
#                     "sticky": True,
#                 },
#             }
#         base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
#         if not base_url:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": "Configuration error",
#                     "message": "Odoo base URL (web.base.url) must be set so Twilio can fetch the dial TwiML.",
#                     "type": "danger",
#                     "sticky": True,
#                 },
#             }
#         twiml_url = base_url + "/twilio/dial?to=" + quote(self.to_number)
#         try:
#             config._twilio_request(
#                 "/2010-04-01/Accounts/%s/Calls.json" % config.account_sid,
#                 method="POST",
#                 data={
#                     "To": self.caller_phone,
#                     "From": self.from_number,
#                     "Url": twiml_url,
#                 },
#             )
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": "Call initiated",
#                     "message": "Your phone will ring shortly. Answer to be connected to %s." % self.to_number,
#                     "type": "success",
#                     "sticky": False,
#                 },
#             }
#         except ValueError as e:
#             return {
#                 "type": "ir.actions.client",
#                 "tag": "display_notification",
#                 "params": {
#                     "title": "Call failed",
#                     "message": str(e),
#                     "type": "danger",
#                     "sticky": True,
#                 },
#             }
