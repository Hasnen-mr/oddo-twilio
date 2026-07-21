# -*- coding: utf-8 -*-
from odoo import fields, models


class DuplicateContactMergeHistory(models.Model):
    _name = "duplicate.contact.merge.history"
    _description = "Duplicate Contact Merge History"
    _order = "create_date desc"

    survivor_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    merged_id = fields.Many2one("res.partner", ondelete="set null", index=True)
    survivor_name = fields.Char()
    merged_name = fields.Char()
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
