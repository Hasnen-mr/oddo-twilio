# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TwilioSmsWorkspace(models.TransientModel):
    """Virtual Workspace Model for SMS Dashboard."""
    _name = "twilio.sms.workspace"
    _description = "Twilio SMS Workspace"

    name = fields.Char(string="Workspace Name", default="SMS Workspace")
    logs_count = fields.Integer(string="SMS Logs Count", compute="_compute_counts")
    templates_count = fields.Integer(string="Templates Count", compute="_compute_counts")
    quick_replies_count = fields.Integer(string="Quick Replies Count", compute="_compute_counts")
    categories_count = fields.Integer(string="Categories Count", compute="_compute_counts")

    @api.depends_context("uid")
    def _compute_counts(self):
        for rec in self:
            rec.templates_count = self.env["twilio.sms.template"].search_count([("active", "=", True)])
            rec.quick_replies_count = self.env["twilio.sms.quick.reply"].search_count([("active", "=", True)])
            rec.categories_count = self.env["twilio.sms.template.category"].search_count([])
            rec.logs_count = self.env["twilio.sms.log"].search_count([])

    @api.model
    def _get_or_create_record(self):
        rec = self.search([], order="id desc", limit=1)
        if not rec:
            rec = self.create({"name": "SMS Workspace"})
        return rec

    def web_read(self, specification):
        records = self.exists()
        if not records:
            rec = self._get_or_create_record()
            res = rec.web_read(specification)
            if res and self.ids:
                res[0]["id"] = self.ids[0]
            return res
        return super().web_read(specification)

    def read(self, fields=None, load='_classic_read'):
        records = self.exists()
        if not records:
            rec = self._get_or_create_record()
            res = rec.read(fields=fields, load=load)
            if res and self.ids:
                res[0]["id"] = self.ids[0]
            return res
        return super().read(fields=fields, load=load)

