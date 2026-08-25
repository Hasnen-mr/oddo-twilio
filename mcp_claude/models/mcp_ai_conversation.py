# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class MCPAIConversation(models.Model):
    _name = "mcp.ai.conversation"
    _description = "MCP AI Conversation Thread (Hybrid Scope Architecture)"
    _order = "id desc"

    name = fields.Char(string="Conversation Title", required=True, default="New Conversation")
    session_id = fields.Many2one("mcp.ai.session", string="Session", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="User", required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    
    scope = fields.Selection([
        ('record', 'Current Record'),
        ('module', 'Current Module'),
        ('workspace', 'Workspace App'),
        ('global', 'Global Assistant')
    ], string="Scope", default='global', required=True, help="Hybrid scope context hierarchy")

    current_model = fields.Char(string="Active Model Context", help="Target Odoo model name, e.g. res.partner")
    current_res_id = fields.Integer(string="Active Record ID", help="Target Odoo record ID")
    workspace_app = fields.Char(string="Workspace App Name", help="e.g. sale, crm, account, twilio")
    
    state = fields.Selection([
        ('idle', 'Idle'),
        ('thinking', 'Thinking'),
        ('streaming', 'Streaming'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string="State", default='idle', required=True)

    schema_version = fields.Integer(string="Schema Version", default=2, required=True)
    message_ids = fields.One2many("mcp.ai.message", "conversation_id", string="Messages")
    message_count = fields.Integer(string="Message Count", compute="_compute_message_count")

    @api.depends("message_ids")
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)
