# -*- coding: utf-8 -*-
from odoo import fields, models


class DuplicateContactHubScanLine(models.TransientModel):
    _name = "duplicate.contact.hub.scan.line"
    _description = "Hub Scan Report Line"
    _order = "date_start desc"

    hub_id = fields.Many2one("duplicate.contact.hub", ondelete="cascade")
    scan_log_id = fields.Many2one("duplicate.contact.scan.log", readonly=True)
    name = fields.Char(related="scan_log_id.name", readonly=True)
    source = fields.Selection(related="scan_log_id.source", readonly=True)
    state = fields.Selection(related="scan_log_id.state", readonly=True)
    progress = fields.Float(related="scan_log_id.progress", readonly=True)
    processed_contacts = fields.Integer(related="scan_log_id.processed_contacts", readonly=True)
    total_contacts = fields.Integer(related="scan_log_id.total_contacts", readonly=True)
    pairs_created = fields.Integer(related="scan_log_id.pairs_created", readonly=True)
    pairs_updated = fields.Integer(related="scan_log_id.pairs_updated", readonly=True)
    date_start = fields.Datetime(related="scan_log_id.date_start", readonly=True)
    date_end = fields.Datetime(related="scan_log_id.date_end", readonly=True)
    user_id = fields.Many2one(related="scan_log_id.user_id", readonly=True)
