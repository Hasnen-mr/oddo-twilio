# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.normalization import normalize_email, normalize_phone
from ..services.similarity import compare_partners

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    duplicate_pair_count = fields.Integer(compute="_compute_duplicate_pair_count")

    def _compute_duplicate_pair_count(self):
        Pair = self.env["duplicate.contact.pair"]
        for partner in self:
            partner.duplicate_pair_count = Pair.search_count([
                ("state", "in", ("open", "review")),
                "|",
                ("partner_a_id", "=", partner.id),
                ("partner_b_id", "=", partner.id),
            ])

    @api.model
    def _duplicate_rules(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "match_name": icp.get_param("duplicate_contact.match_name", "True") == "True",
            "match_phone": icp.get_param("duplicate_contact.match_phone", "True") == "True",
            "match_email": icp.get_param("duplicate_contact.match_email", "True") == "True",
            "match_vat": icp.get_param("duplicate_contact.match_vat", "True") == "True",
            "match_company": icp.get_param("duplicate_contact.match_company", "True") == "True",
            "match_website": icp.get_param("duplicate_contact.match_website", "True") == "True",
            "match_address": icp.get_param("duplicate_contact.match_address", "True") == "True",
            "review_threshold": float(
                icp.get_param("duplicate_contact.review_threshold", "90") or 90
            ),
            "min_threshold": float(
                icp.get_param("duplicate_contact.min_threshold", "72") or 72
            ),
        }

    @api.model
    def _find_probable_duplicates(self, vals, limit=5):
        """Find existing partners matching incoming vals (API / import / create)."""
        rules = self._duplicate_rules()
        domain = [("active", "=", True)]
        candidates = self.browse()

        email = normalize_email(vals.get("email"))
        if email:
            candidates |= self.search(domain + [("email", "ilike", email)], limit=50)

        for phone_field in ("phone", "mobile"):
            norm = normalize_phone(vals.get(phone_field))
            if norm:
                for field in ("phone", "mobile"):
                    chunk = self.search(domain, limit=500)
                    for partner in chunk:
                        if normalize_phone(partner[field]) == norm:
                            candidates |= partner

        vat = (vals.get("vat") or "").replace(" ", "").upper()
        if vat:
            candidates |= self.search(domain + [("vat", "=ilike", vat)], limit=20)

        name = (vals.get("name") or "").strip()
        if name and len(name) >= 3:
            candidates |= self.search(domain + [("name", "ilike", name)], limit=30)

        candidates = candidates.filtered(lambda p: p.active)
        if not candidates:
            return self.browse()

        probe = self.new(vals)
        scored = []
        for candidate in candidates:
            confidence, reasons = compare_partners(probe, candidate, rules)
            if confidence >= rules["min_threshold"]:
                scored.append((confidence, candidate, reasons))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    @api.model_create_multi
    def create(self, vals_list):
        icp = self.env["ir.config_parameter"].sudo()
        api_block = icp.get_param("duplicate_contact.api_block", "False") == "True"
        api_warn = icp.get_param("duplicate_contact.api_warn", "True") == "True"
        from_api = self.env.context.get("duplicate_contact_api_check")

        for vals in vals_list:
            if from_api or self.env.context.get("import_file"):
                matches = self._find_probable_duplicates(vals)
                if matches and api_block:
                    best = matches[0]
                    raise UserError(
                        "Duplicate contact detected (%(conf)s%%): %(name)s"
                        % {"conf": int(best[0]), "name": best[1].display_name}
                    )
                if matches and api_warn and not self.env.context.get("duplicate_contact_force"):
                    best = matches[0]
                    _logger.warning(
                        "Possible duplicate on create: %s (%.0f%%)",
                        best[1].display_name,
                        best[0],
                    )
        return super().create(vals_list)

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = args or []
        if name:
            norm = normalize_phone(name)
            if norm and len(norm) >= 6:
                phone_domain = [
                    "|",
                    ("phone", "ilike", norm[-10:]),
                    ("mobile", "ilike", norm[-10:]),
                ]
                partners = self.search(args + phone_domain, limit=limit)
                if partners:
                    return partners.name_get()
        return super().name_search(name, args, operator, limit)

    def action_view_duplicate_pairs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Duplicates",
            "res_model": "duplicate.contact.pair",
            "view_mode": "list,form",
            "domain": [
                ("state", "in", ("open", "review")),
                "|",
                ("partner_a_id", "=", self.id),
                ("partner_b_id", "=", self.id),
            ],
        }
