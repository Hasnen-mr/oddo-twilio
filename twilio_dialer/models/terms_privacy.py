# -*- coding: utf-8 -*-
from odoo import models


class TwilioTermsPrivacy(models.TransientModel):
    _name = "twilio.terms.privacy"
    _description = "Terms & Privacy"

    def action_open_terms_privacy(self):
        """Open About Us on the Terms & Privacy section."""
        return self.env["twilio.contact.us"].action_open_contact_us(section="terms")
