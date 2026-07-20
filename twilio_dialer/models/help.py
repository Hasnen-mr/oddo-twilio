# -*- coding: utf-8 -*-
from odoo import models


class TwilioHelp(models.TransientModel):
    _name = "twilio.help"
    _description = "Help"

    def action_open_help(self):
        """Open About Us on the Help section."""
        return self.env["twilio.contact.us"].action_open_contact_us(section="help")
