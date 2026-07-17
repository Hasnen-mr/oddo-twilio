# -*- coding: utf-8 -*-
from odoo import models


class TwilioTermsPrivacy(models.TransientModel):
    _name = "twilio.terms.privacy"
    _description = "Terms & Privacy"

    def action_open_terms_privacy(self):
        """Open the Terms & Privacy information page."""
        wizard = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Terms & Privacy",
            "res_model": "twilio.terms.privacy",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "current",
        }
