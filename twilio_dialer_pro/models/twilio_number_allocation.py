# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models


class TwilioNumberAllocation(models.Model):
    _name = "twilio.number.allocation"
    _description = "Twilio Phone Number Allocation"
    _order = "user_id asc"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_login = fields.Char(related="user_id.login", string="Login / Email", readonly=True)

    @api.model
    def _default_twilio_number_ids(self):
        try:
            all_opt = self.env["twilio.phone.number"].sudo().search([("phone_number", "=", "ALL")], limit=1)
            if all_opt:
                return [(6, 0, [all_opt.id])]
        except Exception:
            pass
        return []

    twilio_number_ids = fields.Many2many(
        "twilio.phone.number",
        "twilio_number_allocation_rel",
        "allocation_id",
        "number_id",
        string="Assigned Numbers",
        default=_default_twilio_number_ids,
        help="Select assigned Twilio numbers. Default is 'All numbers'.",
    )

    allocation_status = fields.Char(
        string="Allocation Status",
        compute="_compute_allocation_status",
        store=True,
    )

    @api.depends("twilio_number_ids", "twilio_number_ids.phone_number")
    def _compute_allocation_status(self):
        for rec in self:
            numbers = rec.twilio_number_ids.mapped("phone_number")
            if not numbers or "ALL" in numbers:
                rec.allocation_status = "All Numbers"
            elif len(numbers) == 1:
                rec.allocation_status = f"1 Number ({numbers[0]})"
            else:
                nums_str = ", ".join(numbers)
                rec.allocation_status = f"{len(numbers)} Numbers ({nums_str})"

    def write(self, vals):
        res = super().write(vals)
        if "twilio_number_ids" in vals:
            for rec in self:
                try:
                    self.env["bus.bus"]._sendone(
                        rec.user_id.partner_id,
                        "twilio_number_allocation_updated",
                        {"user_id": rec.user_id.id}
                    )
                except Exception:
                    pass
        return res

    @api.model
    def sync_user_allocations(self):
        """Ensure every non-share active Odoo user has a twilio.number.allocation record with default 'All numbers'."""
        if self.env.context.get("no_sync_user_allocations"):
            return
        try:
            ctx_env = self.with_context(no_sync_user_allocations=True).env
            all_opt = ctx_env["twilio.phone.number"].sudo().search([("phone_number", "=", "ALL")], limit=1)
            if not all_opt:
                all_opt = ctx_env["twilio.phone.number"].sudo().create({
                    "phone_number": "ALL",
                    "friendly_name": "All numbers",
                    "sequence": 0,
                    "sid": "ALL_NUMBERS_OPTION"
                })

            users = ctx_env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])
            existing_allocs = ctx_env["twilio.number.allocation"].sudo().search([])
            existing_user_ids = set(existing_allocs.mapped("user_id.id"))

            empty_allocs = existing_allocs.filtered(lambda a: not a.twilio_number_ids)
            if empty_allocs:
                empty_allocs.sudo().write({"twilio_number_ids": [(6, 0, [all_opt.id])]})

            missing_users = [u for u in users if u.id not in existing_user_ids]
            if missing_users:
                ctx_env["twilio.number.allocation"].sudo().create([
                    {"user_id": u.id, "twilio_number_ids": [(6, 0, [all_opt.id])]}
                    for u in missing_users
                ])
        except Exception:
            pass

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        if not self.env.context.get("no_sync_user_allocations"):
            self.sync_user_allocations()
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, count_limit=None):
        if not self.env.context.get("no_sync_user_allocations"):
            self.sync_user_allocations()
        return super().web_search_read(domain=domain, specification=specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get("no_sync_user_allocations"):
            self.sync_user_allocations()
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)