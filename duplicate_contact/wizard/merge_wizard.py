# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class DuplicateContactMergeWizard(models.TransientModel):
    _name = "duplicate.contact.merge.wizard"
    _description = "Merge Duplicate Contacts"

    pair_id = fields.Many2one("duplicate.contact.pair")
    partner_a_id = fields.Many2one("res.partner", required=True, string="Contact 1")
    partner_b_id = fields.Many2one("res.partner", required=True, string="Contact 2")
    confidence = fields.Float(related="pair_id.confidence", readonly=True)
    match_reasons = fields.Text(related="pair_id.match_reasons", readonly=True)
    survivor_id = fields.Selection(
        [("a", "Contact 1"), ("b", "Contact 2")],
        default="a",
        required=True,
        string="Contact to keep",
    )

    contact_1_title = fields.Char(compute="_compute_contact_labels")
    contact_2_title = fields.Char(compute="_compute_contact_labels")
    contact_1_subtitle = fields.Char(compute="_compute_contact_labels")
    contact_2_subtitle = fields.Char(compute="_compute_contact_labels")
    merge_warning = fields.Char(compute="_compute_contact_labels")

    name_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    email_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    phone_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    mobile_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    street_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    city_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    website_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    vat_choice = fields.Selection([("a", "Contact 1"), ("b", "Contact 2")], default="a")
    combine_notes = fields.Boolean(default=True, string="Combine internal notes")

    preview_name_a = fields.Char(compute="_compute_preview")
    preview_name_b = fields.Char(compute="_compute_preview")
    preview_phone_a = fields.Char(compute="_compute_preview")
    preview_phone_b = fields.Char(compute="_compute_preview")
    preview_mobile_a = fields.Char(compute="_compute_preview")
    preview_mobile_b = fields.Char(compute="_compute_preview")
    preview_email_a = fields.Char(compute="_compute_preview")
    preview_email_b = fields.Char(compute="_compute_preview")
    preview_street_a = fields.Char(compute="_compute_preview")
    preview_street_b = fields.Char(compute="_compute_preview")
    preview_city_a = fields.Char(compute="_compute_preview")
    preview_city_b = fields.Char(compute="_compute_preview")
    preview_website_a = fields.Char(compute="_compute_preview")
    preview_website_b = fields.Char(compute="_compute_preview")
    preview_vat_a = fields.Char(compute="_compute_preview")
    preview_vat_b = fields.Char(compute="_compute_preview")

    @api.depends("partner_a_id", "partner_b_id", "survivor_id")
    def _compute_contact_labels(self):
        for wiz in self:
            a, b = wiz.partner_a_id, wiz.partner_b_id
            wiz.contact_1_title = a.display_name or "Contact 1"
            wiz.contact_2_title = b.display_name or "Contact 2"
            wiz.contact_1_subtitle = wiz._contact_subtitle(a)
            wiz.contact_2_subtitle = wiz._contact_subtitle(b)
            if a and b and a.id == b.id:
                wiz.merge_warning = (
                    "These two sides point to the same contact record. "
                    "This duplicate row is invalid and cannot be merged."
                )
            elif wiz.survivor_id == "a":
                removed = b.display_name if b else "Contact 2"
                kept = a.display_name if a else "Contact 1"
                wiz.merge_warning = (
                    '"%s" will be archived. All data moves into "%s".'
                    % (removed, kept)
                )
            else:
                removed = a.display_name if a else "Contact 1"
                kept = b.display_name if b else "Contact 2"
                wiz.merge_warning = (
                    '"%s" will be archived. All data moves into "%s".'
                    % (removed, kept)
                )

    def _contact_subtitle(self, partner):
        if not partner:
            return ""
        bits = []
        if partner.email:
            bits.append(partner.email)
        phone = partner.phone or partner.mobile
        if phone:
            bits.append(phone)
        if partner.city:
            bits.append(partner.city)
        bits.append("#%s" % partner.id)
        return " · ".join(bits)

    @api.depends("partner_a_id", "partner_b_id")
    def _compute_preview(self):
        empty = {
            "preview_name_a": "",
            "preview_name_b": "",
            "preview_phone_a": "",
            "preview_phone_b": "",
            "preview_mobile_a": "",
            "preview_mobile_b": "",
            "preview_email_a": "",
            "preview_email_b": "",
            "preview_street_a": "",
            "preview_street_b": "",
            "preview_city_a": "",
            "preview_city_b": "",
            "preview_website_a": "",
            "preview_website_b": "",
            "preview_vat_a": "",
            "preview_vat_b": "",
        }
        for wiz in self:
            a, b = wiz.partner_a_id, wiz.partner_b_id
            if not a or not b:
                wiz.update(empty)
                continue
            wiz.preview_name_a = a.name or "—"
            wiz.preview_name_b = b.name or "—"
            wiz.preview_phone_a = a.phone or "—"
            wiz.preview_phone_b = b.phone or "—"
            wiz.preview_mobile_a = a.mobile or "—"
            wiz.preview_mobile_b = b.mobile or "—"
            wiz.preview_email_a = a.email or "—"
            wiz.preview_email_b = b.email or "—"
            wiz.preview_street_a = a.street or "—"
            wiz.preview_street_b = b.street or "—"
            wiz.preview_city_a = a.city or "—"
            wiz.preview_city_b = b.city or "—"
            wiz.preview_website_a = a.website or "—"
            wiz.preview_website_b = b.website or "—"
            wiz.preview_vat_a = a.vat or "—"
            wiz.preview_vat_b = b.vat or "—"

    def _partners(self):
        self.ensure_one()
        if self.survivor_id == "a":
            return self.partner_a_id, self.partner_b_id
        return self.partner_b_id, self.partner_a_id

    def _field_choices(self):
        self.ensure_one()
        return {
            "name": self.name_choice,
            "email": self.email_choice,
            "phone": self.phone_choice,
            "mobile": self.mobile_choice,
            "street": self.street_choice,
            "city": self.city_choice,
            "website": self.website_choice,
            "vat": self.vat_choice,
        }

    def action_merge(self):
        self.ensure_one()
        if not self.partner_a_id or not self.partner_b_id:
            raise UserError("Both contacts are required before merging.")
        if self.partner_a_id.id == self.partner_b_id.id:
            raise UserError(
                "Cannot merge a contact with itself. "
                "Please mark this duplicate row as Not Duplicate or delete it."
            )

        from ..services.merge import DuplicateMergeService
        survivor, duplicate = self._partners()
        if survivor.id == duplicate.id:
            raise UserError("Please choose which contact should be kept.")

        DuplicateMergeService(self.env).merge_partners(
            survivor,
            duplicate,
            field_choices=self._field_choices(),
            combine_notes=self.combine_notes,
            partner_a=self.partner_a_id,
            partner_b=self.partner_b_id,
        )
        if self.pair_id:
            self.pair_id.sudo().write({"state": "merged"})

        from ..services.action_utils import xml_id_action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Merge complete",
                "message": '"%s" (#%s) was merged into "%s" (#%s) and archived.'
                % (
                    duplicate.display_name,
                    duplicate.id,
                    survivor.display_name,
                    survivor.id,
                ),
                "type": "success",
                "sticky": False,
                "next": xml_id_action(
                    self.env,
                    "duplicate_contact.action_duplicate_contact_pairs",
                ),
            },
        }
