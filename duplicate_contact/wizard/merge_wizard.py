# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DuplicateContactMergeWizard(models.TransientModel):
    _name = "duplicate.contact.merge.wizard"
    _description = "Merge Duplicate Contacts"

    pair_id = fields.Many2one("duplicate.contact.pair")
    partner_a_id = fields.Many2one("res.partner", required=True, string="Contact A")
    partner_b_id = fields.Many2one("res.partner", required=True, string="Contact B")
    survivor_id = fields.Selection(
        [("a", "Contact A"), ("b", "Contact B")],
        default="a",
        required=True,
        string="Keep as master",
    )

    name_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    email_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    phone_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    mobile_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    street_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    website_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    vat_choice = fields.Selection([("a", "A"), ("b", "B")], default="a")
    combine_notes = fields.Boolean(default=True)

    preview_name_a = fields.Char(compute="_compute_preview")
    preview_name_b = fields.Char(compute="_compute_preview")
    preview_phone_a = fields.Char(compute="_compute_preview")
    preview_phone_b = fields.Char(compute="_compute_preview")
    preview_email_a = fields.Char(compute="_compute_preview")
    preview_email_b = fields.Char(compute="_compute_preview")

    @api.depends("partner_a_id", "partner_b_id")
    def _compute_preview(self):
        for wiz in self:
            a, b = wiz.partner_a_id, wiz.partner_b_id
            wiz.preview_name_a = a.name
            wiz.preview_name_b = b.name
            wiz.preview_phone_a = a.phone or a.mobile
            wiz.preview_phone_b = b.phone or b.mobile
            wiz.preview_email_a = a.email
            wiz.preview_email_b = b.email

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
            "website": self.website_choice,
            "vat": self.vat_choice,
        }

    def action_merge(self):
        self.ensure_one()
        from ..services.merge import DuplicateMergeService
        survivor, duplicate = self._partners()
        DuplicateMergeService(self.env).merge_partners(
            survivor,
            duplicate,
            field_choices=self._field_choices(),
            combine_notes=self.combine_notes,
            partner_a=self.partner_a_id,
            partner_b=self.partner_b_id,
        )
        if self.pair_id:
            self.pair_id.state = "merged"
        return {
            "type": "ir.actions.act_window",
            "name": survivor.name,
            "res_model": "res.partner",
            "res_id": survivor.id,
            "view_mode": "form",
            "target": "current",
        }
