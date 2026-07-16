# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_twilio_call(self):
        """Open Power Dialer prefilled with this contact's phone/mobile."""
        self.ensure_one()
        number = (self.mobile or self.phone or "").strip()
        if not number:
            raise UserError("Add a Phone or Mobile number on this contact before calling.")
        return {
            "type": "ir.actions.client",
            "tag": "twilio_dialer.open_dialer",
            "params": {
                "phone": number,
                "partner_id": self.id,
                "partner_name": self.display_name,
            },
        }
