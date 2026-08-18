# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    twilio_number_ids = fields.Many2many(
        "twilio.phone.number",
        "res_users_twilio_phone_number_rel",
        "user_id",
        "number_id",
        string="Assigned Twilio Numbers",
        help="Select Twilio phone numbers assigned to this user. If empty, the user has access to all numbers by default.",
    )
    assigned_numbers_display = fields.Char(
        string="Assigned Numbers",
        compute="_compute_assigned_numbers_display",
        store=False,
    )

    @api.depends("twilio_number_ids", "twilio_number_ids.phone_number")
    def _compute_assigned_numbers_display(self):
        for user in self:
            alloc = self.env["twilio.number.allocation"].sudo().search([("user_id", "=", user.id)], limit=1)
            if alloc and alloc.twilio_number_ids:
                nums = alloc.twilio_number_ids.mapped("phone_number")
                if "ALL" in nums or not nums:
                    user.assigned_numbers_display = "All Numbers"
                else:
                    user.assigned_numbers_display = ", ".join(nums)
            elif user.twilio_number_ids:
                nums = user.twilio_number_ids.mapped("phone_number")
                if "ALL" in nums or not nums:
                    user.assigned_numbers_display = "All Numbers"
                else:
                    user.assigned_numbers_display = ", ".join(nums)
            else:
                user.assigned_numbers_display = "All Numbers"

    def get_allowed_twilio_numbers(self):
        """Return list of allowed phone_number strings for this user.
        If 'ALL' or empty is assigned, returns empty list (meaning ALL numbers allowed in dialpad).
        """
        self.ensure_one()
        alloc = self.env["twilio.number.allocation"].sudo().search([("user_id", "=", self.id)], limit=1)
        if alloc and alloc.twilio_number_ids:
            nums = alloc.twilio_number_ids.mapped("phone_number")
            if "ALL" in nums or not nums:
                return []
            return [n for n in nums if n != "ALL"]
        if self.twilio_number_ids:
            nums = self.twilio_number_ids.mapped("phone_number")
            if "ALL" in nums or not nums:
                return []
            return [n for n in nums if n != "ALL"]
        return []