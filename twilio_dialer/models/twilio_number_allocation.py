# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class TwilioNumberAllocation(models.Model):
    _name = "twilio.number.allocation"
    _description = "Twilio Phone Number User Allocation"
    _rec_name = "user_name"
    _order = "user_name asc"

    user_id = fields.Many2one("res.users", string="User", required=True, ondelete="cascade", index=True)
    user_name = fields.Char(related="user_id.name", string="User Name", store=True)
    user_login = fields.Char(related="user_id.login", string="Login / Email", store=True)
    user_email = fields.Char(related="user_id.email", string="Email", store=True)
    active = fields.Boolean(related="user_id.active", string="Active User", store=True)
    company_id = fields.Many2one(related="user_id.company_id", string="Company", store=True)
    
    twilio_number_ids = fields.Many2many(
        "twilio.phone.number",
        "twilio_number_allocation_rel",
        "allocation_id",
        "number_id",
        string="Allocated Twilio Numbers",
        help="Specific Twilio phone numbers assigned to this user.",
    )
    
    number_count = fields.Integer(
        string="Assigned Count",
        compute="_compute_allocation_summary",
        store=False,
    )
    allocation_status = fields.Char(
        string="Allocation Status",
        compute="_compute_allocation_summary",
        store=False,
    )
    
    @api.depends("twilio_number_ids", "twilio_number_ids.phone_number", "twilio_number_ids.active")
    def _compute_allocation_summary(self):
        for rec in self:
            nums = rec.twilio_number_ids.filtered(lambda n: n.active)
            if any(n.phone_number == "NONE" for n in nums):
                rec.number_count = 0
                rec.allocation_status = "No Number (Disabled)"
            elif not nums or any(n.phone_number == "ALL" for n in nums):
                rec.number_count = 0
                rec.allocation_status = "All Numbers"
            else:
                real_nums = nums.filtered(lambda n: n.phone_number not in ("ALL", "NONE"))
                count = len(real_nums)
                rec.number_count = count
                rec.allocation_status = f"{count} Number" if count == 1 else f"{count} Numbers"

    def write(self, vals):
        res = super().write(vals)
        if "twilio_number_ids" in vals and self.env.get("bus.bus"):
            try:
                for rec in self:
                    partner = rec.user_id.partner_id
                    if partner:
                        self.env["bus.bus"]._sendone(
                            partner,
                            "twilio_number_allocation_updated",
                            {"user_id": rec.user_id.id},
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
            none_opt = ctx_env["twilio.phone.number"].sudo().search([("phone_number", "=", "NONE")], limit=1)
            if not none_opt:
                none_opt = ctx_env["twilio.phone.number"].sudo().create({
                    "phone_number": "NONE",
                    "friendly_name": "No number",
                    "sequence": 9999,
                    "sid": "NO_NUMBERS_OPTION"
                })
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
    def _get_current_twilio_admin_id(self):
        """Retrieve the UID of the single designated Twilio Admin."""
        admin_id_str = self.env["ir.config_parameter"].sudo().get_param("twilio_dialer.admin_user_id")
        if admin_id_str:
            try:
                admin_uid = int(admin_id_str)
                user = self.env["res.users"].sudo().browse(admin_uid)
                if user.exists() and user.active:
                    return admin_uid
            except (ValueError, TypeError):
                pass
        
        # Fallback to root admin (UID 2 or first system admin)
        root_admin = self.env["res.users"].sudo().search([("id", "=", 2), ("active", "=", True)], limit=1)
        if not root_admin:
            root_admin = self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)], order="id asc", limit=1)
        
        if root_admin:
            self.env["ir.config_parameter"].sudo().set_param("twilio_dialer.admin_user_id", str(root_admin.id))
            return root_admin.id
        return 2

    @api.model
    def _is_current_twilio_admin(self, user=None):
        """Check if user (or current user) is the designated Twilio Admin or Superuser."""
        target_uid = user.id if user else self.env.user.id
        if target_uid == 1:  # Superuser is always admin
            return True
        admin_uid = self._get_current_twilio_admin_id()
        return target_uid == admin_uid

    @api.model
    def action_transfer_admin(self, new_user_id):
        """Transfer the single Twilio Admin privilege to another user."""
        if not self._is_current_twilio_admin():
            from odoo.exceptions import AccessError
            raise AccessError(_("Only the current Twilio Admin can transfer admin privileges."))
        
        new_user = self.env["res.users"].sudo().browse(new_user_id)
        if not new_user.exists() or not new_user.active or new_user.share:
            return {"success": False, "message": "Invalid user selected for admin transfer."}
        
        self.env["ir.config_parameter"].sudo().set_param("twilio_dialer.admin_user_id", str(new_user.id))
        _logger.info("Twilio Admin privileges transferred from UID %s to UID %s (%s)", self.env.user.id, new_user.id, new_user.name)
        return self.get_allocation_data()

    @api.model
    def get_allocation_data(self):
        """Return all phone numbers and user allocation records for the UI."""
        self.sync_user_allocations()
        self.env["twilio.phone.number"].sudo()._auto_sync_cached_numbers()

        numbers = self.env["twilio.phone.number"].sudo().search([("active", "=", True)], order="sequence asc, phone_number asc")
        allocations = self.sudo().search([], order="user_id asc")

        num_data = [
            {
                "id": n.id,
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name or n.phone_number,
                "display_name": n.display_name or n.phone_number,
                "is_all": n.phone_number == "ALL",
                "is_none": n.phone_number == "NONE",
            }
            for n in numbers
        ]

        current_admin_id = self._get_current_twilio_admin_id()
        current_user_is_admin = self._is_current_twilio_admin()

        # Compute calls count per user
        call_logs = self.env["twilio.call.log"].sudo().search([])
        calls_per_user = {}
        for log in call_logs:
            if log.user_id:
                calls_per_user[log.user_id.id] = calls_per_user.get(log.user_id.id, 0) + 1

        alloc_data = [
            {
                "id": a.id,
                "user_id": a.user_id.id,
                "partner_id": a.user_id.partner_id.id,
                "user_name": a.user_id.name or "Unknown User",
                "user_login": a.user_login or "",
                "user_email": a.user_email or a.user_login or "",
                "number_ids": a.twilio_number_ids.ids,
                "status": a.allocation_status or "All Numbers",
                "is_admin": a.user_id.id == current_admin_id,
                "calls_count": calls_per_user.get(a.user_id.id, 0),
                "im_status": getattr(a.user_id, "im_status", False) or getattr(a.user_id.partner_id, "im_status", "offline") or "offline",
            }
            for a in allocations
        ]

        return {
            "success": True,
            "numbers": num_data,
            "allocations": alloc_data,
            "current_user_is_admin": True,
            "admin_user_id": current_admin_id,
        }

    @api.model
    def update_allocation(self, allocation_id, number_ids):
        """Update assigned phone numbers for a specific user allocation."""
        alloc = self.sudo().browse(allocation_id)
        if not alloc.exists():
            return {"success": False, "message": "Record not found"}

        if not number_ids:
            none_opt = self.env["twilio.phone.number"].sudo().search([("phone_number", "=", "NONE")], limit=1)
            if not none_opt:
                none_opt = self.env["twilio.phone.number"].sudo().create({
                    "phone_number": "NONE",
                    "friendly_name": "No number",
                    "sequence": 9999,
                    "sid": "NO_NUMBERS_OPTION"
                })
            number_ids = [none_opt.id]

        alloc.write({"twilio_number_ids": [(6, 0, number_ids)]})
        if hasattr(alloc.user_id, "twilio_number_ids"):
            alloc.user_id.sudo().write({"twilio_number_ids": [(6, 0, number_ids)]})

        return self.get_allocation_data()

    @api.model
    def reset_all_to_default(self):
        """Reset all users to 'All Numbers'."""
        all_opt = self.env["twilio.phone.number"].sudo().search([("phone_number", "=", "ALL")], limit=1)
        if not all_opt:
            all_opt = self.env["twilio.phone.number"].sudo().create({
                "phone_number": "ALL",
                "friendly_name": "All numbers",
                "sequence": 0,
                "sid": "ALL_NUMBERS_OPTION"
            })
        self.sudo().search([]).write({"twilio_number_ids": [(6, 0, [all_opt.id])]})
        return self.get_allocation_data()

    @api.model
    def get_user_allowed_numbers(self, user_id=None):
        """Return the list of phone number dicts that user_id is authorized to use for outbound and inbound."""
        if not user_id:
            user_id = self.env.user.id
            
        self.sync_user_allocations()
        self.env["twilio.phone.number"].sudo()._auto_sync_cached_numbers()
        
        all_active = self.env["twilio.phone.number"].sudo().search(
            [("active", "=", True), ("phone_number", "not in", ("ALL", "NONE"))],
            order="sequence asc, phone_number asc"
        )
        
        alloc = self.sudo().search([("user_id", "=", user_id)], limit=1)
        if not alloc or not alloc.twilio_number_ids:
            allowed_recs = all_active
        else:
            nums = alloc.twilio_number_ids.filtered(lambda n: n.active)
            if any(n.phone_number == "NONE" for n in nums):
                return []
            elif any(n.phone_number == "ALL" for n in nums):
                allowed_recs = all_active
            else:
                allowed_recs = nums.filtered(lambda n: n.phone_number not in ("ALL", "NONE"))
                
        if not allowed_recs:
            allowed_recs = all_active

        return [
            {
                "id": n.id,
                "phone_number": n.phone_number,
                "friendly_name": n.friendly_name or n.phone_number,
                "display_name": n.display_name or f"{n.friendly_name or n.phone_number} ({n.phone_number})",
                "type": "incoming",
            }
            for n in allowed_recs
        ]

    @api.model
    def get_users_for_number(self, phone_number):
        """Return the active res.users records authorized to receive calls on phone_number."""
        self.sync_user_allocations()
        self.env["twilio.phone.number"].sudo()._auto_sync_cached_numbers()

        if not phone_number:
            return self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])

        import re
        clean_target = re.sub(r"\D", "", str(phone_number or ""))
        clean_target_10 = clean_target[1:] if len(clean_target) > 10 and clean_target.startswith("1") else (clean_target[-10:] if len(clean_target) >= 10 else clean_target)

        all_nums = self.env["twilio.phone.number"].sudo().search([("active", "=", True)])
        target_number_ids = set()
        all_opt_ids = set()

        for n in all_nums:
            if n.phone_number == "ALL":
                all_opt_ids.add(n.id)
                continue
            clean_n = re.sub(r"\D", "", str(n.phone_number or ""))
            clean_n_10 = clean_n[1:] if len(clean_n) > 10 and clean_n.startswith("1") else (clean_n[-10:] if len(clean_n) >= 10 else clean_n)
            if clean_n == clean_target or (clean_target_10 and clean_n_10 == clean_target_10):
                target_number_ids.add(n.id)

        allocations = self.sudo().search([])
        authorized_user_ids = set()

        for alloc in allocations:
            if not alloc.user_id or not alloc.user_id.active:
                continue
            u_nums = set(alloc.twilio_number_ids.ids)
            has_all = not u_nums or bool(u_nums & all_opt_ids)
            has_specific = bool(u_nums & target_number_ids)
            if has_all or has_specific:
                authorized_user_ids.add(alloc.user_id.id)

        if not authorized_user_ids:
            return self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True)])

        return self.env["res.users"].sudo().browse(list(authorized_user_ids))
