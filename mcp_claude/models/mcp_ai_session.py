# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class MCPAISession(models.Model):
    _name = "mcp.ai.session"
    _description = "MCP AI User Workspace Session"
    _order = "id desc"

    name = fields.Char(string="Session Name", required=True, default="New Session")
    user_id = fields.Many2one("res.users", string="User", required=True, default=lambda self: self.env.user, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string="Active", default=True)
    device_info = fields.Char(string="Device Info")
    schema_version = fields.Integer(string="Schema Version", default=1, required=True)

    conversation_ids = fields.One2many("mcp.ai.conversation", "session_id", string="Conversations")
    conversation_count = fields.Integer(string="Conversation Count", compute="_compute_conversation_count")

    @api.depends("conversation_ids")
    def _compute_conversation_count(self):
        for rec in self:
            rec.conversation_count = len(rec.conversation_ids)
