# -*- coding: utf-8 -*-
from odoo import models


class TwilioHelp(models.TransientModel):
    _name = "twilio.help"
    _description = "Help"

    def action_open_help(self):
        """Open the Help information page."""
        wizard = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Help",
            "res_model": "twilio.help",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "current",
        }
