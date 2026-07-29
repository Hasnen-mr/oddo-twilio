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

    total_selected_count = fields.Integer(
        string="Total Selected",
        compute="_compute_contact_stats",
    )
    valid_phone_count = fields.Integer(
        string="Valid Phone Numbers",
        compute="_compute_contact_stats",
    )
    no_phone_count = fields.Integer(
        string="Missing Phone Numbers",
        compute="_compute_contact_stats",
    )
    duplicate_count = fields.Integer(
        string="Duplicate Numbers",
        compute="_compute_contact_stats",
    )
    estimated_size = fields.Integer(
        string="Estimated Campaign Size",
        compute="_compute_contact_stats",
    )

    @api.depends("partner_ids", "dialer_id", "target_type")
    def _compute_contact_stats(self):
        for rec in self:
            partners = rec.partner_ids
            rec.total_selected_count = len(partners)
            valid = 0
            no_phone = 0
            seen_phones = set()
            duplicates = 0

            # Get existing queue phones if adding to existing queue
            if rec.target_type == "existing" and rec.dialer_id:
                for line in rec.dialer_id.queue_line_ids:
                    if line.phone:
                        clean = "".join(c for c in line.phone if c.isdigit())
                        if clean:
                            seen_phones.add(clean)

            for partner in partners:
                # Phone priority: mobile -> phone
                raw = partner.mobile or partner.phone or ""
                digits = "".join(c for c in raw if c.isdigit())
                if not raw or not digits:
                    no_phone += 1
                elif digits in seen_phones:
                    duplicates += 1
                else:
                    valid += 1
                    seen_phones.add(digits)

            rec.valid_phone_count = valid
            rec.no_phone_count = no_phone
            rec.duplicate_count = duplicates
            rec.estimated_size = valid

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
