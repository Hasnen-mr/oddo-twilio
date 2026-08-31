# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models


class TwilioPhoneNumber(models.Model):
    _name = "twilio.phone.number"
    _description = "Twilio Phone Number"
    _order = "sequence asc, phone_number asc"
    _rec_name = "display_name"

    sequence = fields.Integer(string="Sequence", default=10)
    phone_number = fields.Char(string="Phone Number", required=True, index=True)
    friendly_name = fields.Char(string="Friendly Name")
    sid = fields.Char(string="Twilio SID", index=True)
    active = fields.Boolean(string="Active", default=True)
    user_ids = fields.Many2many(
        "res.users",
        "res_users_twilio_phone_number_rel",
        "number_id",
        "user_id",
        string="Assigned Users",
        help="Users assigned to use this phone number. If empty, all users can use this number by default.",
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("phone_number", "friendly_name")
    def _compute_display_name(self):
        for rec in self:
            if rec.phone_number == "ALL":
                rec.display_name = "All numbers"
            elif rec.friendly_name and rec.friendly_name != rec.phone_number:
                rec.display_name = f"{rec.friendly_name} ({rec.phone_number})"
            else:
                rec.display_name = rec.phone_number or ""

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if not self.env.context.get("no_sync_user_allocations"):
            self._auto_sync_cached_numbers()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if not self.env.context.get("no_sync_user_allocations"):
            self._auto_sync_cached_numbers()
        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

    @api.model
    def _auto_sync_cached_numbers(self):
        """Auto-populate twilio.phone.number records including the 'All numbers' first option and any Twilio numbers."""
        try:
            PhoneNumber = self.sudo()
            # 1. Ensure 'All numbers' first option exists
            all_option = PhoneNumber.search([("phone_number", "=", "ALL")], limit=1)
            if not all_option:
                PhoneNumber.create({
                    "phone_number": "ALL",
                    "friendly_name": "All numbers",
                    "sequence": 0,
                    "sid": "ALL_NUMBERS_OPTION"
                })

            # 2. Sync cached numbers from ICP
            icp = self.env["ir.config_parameter"].sudo()
            cached_json = icp.get_param("twilio_dialer.incoming_phone_numbers", "[]")
            try:
                phone_list = json.loads(cached_json) if cached_json else []
            except Exception:
                phone_list = []

            single_num = icp.get_param("twilio_dialer.phone_number")
            if single_num and not any(isinstance(p, dict) and p.get("phone_number") == single_num for p in phone_list):
                phone_list.append({"phone_number": single_num, "friendly_name": single_num, "sid": ""})

            existing_db = {rec.phone_number: rec for rec in PhoneNumber.search([])}
            for p in phone_list:
                if not isinstance(p, dict):
                    continue
                num = p.get("phone_number")
                if not num or num == "ALL":
                    continue
                fname = p.get("friendly_name") or num
                sid = p.get("sid") or ""
                if num not in existing_db:
                    created = PhoneNumber.create({
                        "phone_number": num,
                        "friendly_name": fname,
                        "sid": sid,
                        "sequence": 10,
                        "active": True,
                    })
                    existing_db[num] = created
                else:
                    vals = {}
                    if fname and existing_db[num].friendly_name != fname:
                        vals["friendly_name"] = fname
                    if sid and existing_db[num].sid != sid:
                        vals["sid"] = sid
                    if vals:
                        existing_db[num].write(vals)
        except Exception:
            pass
