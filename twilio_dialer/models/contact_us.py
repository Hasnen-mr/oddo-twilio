# -*- coding: utf-8 -*-
from odoo import models


class TwilioContactUs(models.TransientModel):
    _name = "twilio.contact.us"
    _description = "Contact Us"

    def action_open_contact_us(self):
        """Open the Contact Us information page."""
        wizard = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Contact Us",
            "res_model": "twilio.contact.us",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "current",
        }
