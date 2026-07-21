# -*- coding: utf-8 -*-
from odoo import fields, models


class DuplicateContactHubMergeLine(models.TransientModel):
    _name = "duplicate.contact.hub.merge.line"
    _description = "Hub Merge History Line"
    _order = "create_date desc"

    hub_id = fields.Many2one("duplicate.contact.hub", ondelete="cascade")
    history_id = fields.Many2one("duplicate.contact.merge.history", readonly=True)
    create_date = fields.Datetime(related="history_id.create_date", readonly=True)
    survivor_name = fields.Char(related="history_id.survivor_name", readonly=True)
    merged_name = fields.Char(related="history_id.merged_name", readonly=True)
    survivor_id = fields.Many2one(related="history_id.survivor_id", readonly=True)
    merged_id = fields.Many2one(related="history_id.merged_id", readonly=True)
    user_id = fields.Many2one(related="history_id.user_id", readonly=True)
