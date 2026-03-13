from urllib.parse import quote
from odoo import api, fields, models

class ClickToCallWizard(models.TransientModel):
    _name = "twilio.click.to.call.wizard"
    _description = "Click-to-call via Twilio"

    from_number = fields.Selection(selection="_selection_from_number", string="From (Twilio number)", required=True)
    country_code = fields.Selection([
    ('+91', 'IN +91'),
    ('+1', 'US +1'),
    ('+52', 'MX +52'),
    ('+53', 'CU +53'),
], default='+91', string="Country Code")
    to_number = fields.Char("To (contact number)")
    # caller_phone = fields.Char("Your phone", required=True)
    caller_phone = fields.Char("Your phone")

    record_call = fields.Boolean("Record Call")
    incoming_call = fields.Boolean("Incoming Call")

    # -------------------------------------------------------------------------
    # Dialpad helpers
    # -------------------------------------------------------------------------
    # def _reopen_wizard(self):
    #     """Return an action that reopens this wizard with the same record."""
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': self._name,
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'res_id': self.id,
    #         'context': self.env.context,
    #     }
    

    def press_1(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "1"
        # return self._reopen_wizard()

    def press_2(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "2"
        # return self._reopen_wizard()

    def press_3(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "3"
        # return self._reopen_wizard()

    def press_4(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "4"
        # return self._reopen_wizard()

    def press_5(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "5"
        # return self._reopen_wizard()

    def press_6(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "6"
        # return self._reopen_wizard()

    def press_7(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "7"
        # return self._reopen_wizard()

    def press_8(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "8"
        # return self._reopen_wizard()

    def press_9(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "9"
        # return self._reopen_wizard()

    def press_0(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "0"
        # return self._reopen_wizard()

    def press_star(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "*"
        # return self._reopen_wizard()

    def press_hash(self):
        self.ensure_one()
        self.to_number = (self.to_number or "") + "#"
        # return self._reopen_wizard()
    
    def action_refresh_numbers(self):
        # return self._reopen_wizard()
        return True

    def action_recent_calls(self):
        return True
    
    def action_fetch_calls(self):

        wizard = self.env["twilio.fetch.calls.wizard"].create({})
        return wizard.action_fetch()
    
    def action_close_dialer(self):
        return {
        "type": "ir.actions.act_window_close"
    }
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
    def action_record_call(self):
        self.ensure_one()

        return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {
            "title": "Record Call",
            "message": "Call recording feature coming soon.",
            "type": "info",
        },
    }


    def action_incoming_call(self):
        self.ensure_one()

        return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {
            "title": "Incoming Call",
            "message": "Incoming call feature coming soon.",
            "type": "info",
        },
    }

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
        # twiml_url = base_url + "/twilio/dial?to=" + quote(self.to_number)
        full_number = f"{self.country_code}{self.to_number}"
        twiml_url = base_url + "/twilio/dial?to=" + quote(full_number)
        try:
            config._twilio_request(
                "/2010-04-01/Accounts/%s/Calls.json" % config.account_sid,
                method="POST",
                data={
                    "To": self.caller_phone or full_number,
                    "From": self.from_number,
                    "Url": twiml_url,
                },
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Call initiated",
                    "message": "Your phone will ring shortly. Answer to be connected to %s." % full_number,
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


    def action_redial(self):

        self.ensure_one()

        if not self.to_number:
         return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Redial",
                "message": "No number to redial",
                "type": "warning",
            },
        }

        return self.action_initiate_call()