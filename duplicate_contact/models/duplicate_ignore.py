# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DuplicateContactIgnore(models.Model):
    _name = "duplicate.contact.ignore"
    _description = "Duplicate Contact Ignore List"
    _rec_name = "display_name"

    partner_low_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    partner_high_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    reason = fields.Char()
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("partner_low_id", "partner_high_id", "partner_low_id.name", "partner_high_id.name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s ↔ %s" % (
                record.partner_low_id.display_name,
                record.partner_high_id.display_name,
            )
