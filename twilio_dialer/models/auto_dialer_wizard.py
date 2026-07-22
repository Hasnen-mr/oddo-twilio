# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class TwilioAutoDialerAddContactsWizard(models.TransientModel):
    _name = "twilio.auto.dialer.add.contacts.wizard"
    _description = "Add Contacts to Auto Dialer Queue"

    target_type = fields.Selection(
        [
            ("new", "Create New Queue"),
            ("existing", "Existing Queue"),
        ],
        string="Add To",
        default="new",
        required=True,
    )
    campaign_name = fields.Char(
        string="Queue Name",
        default="New Dialing Queue",
    )
    dialer_id = fields.Many2one(
        "twilio.auto.dialer",
        string="Existing Queue",
        domain="[('state', 'in', ('draft', 'paused'))]",
    )
    partner_ids = fields.Many2many(
        "res.partner",
        string="Contacts",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "res.partner" and self.env.context.get("active_ids"):
            res["partner_ids"] = [(6, 0, self.env.context.get("active_ids"))]
        return res

    def action_add_to_queue(self):
        self.ensure_one()
        if not self.partner_ids:
            raise UserError("Please select at least one contact.")

        if self.target_type == "new":
            if not self.campaign_name:
                raise UserError("Please provide a name for the new queue.")
            dialer = self.env["twilio.auto.dialer"].create({
                "name": self.campaign_name,
                "user_id": self.env.user.id,
                "state": "draft",
            })
        else:
            if not self.dialer_id:
                raise UserError("Please select an existing Queue.")
            dialer = self.dialer_id

        res = dialer.action_add_contacts(self.partner_ids)

        return {
            "name": dialer.name,
            "type": "ir.actions.act_window",
            "res_model": "twilio.auto.dialer",
            "res_id": dialer.id,
            "view_mode": "form",
            "target": "current",
        }
