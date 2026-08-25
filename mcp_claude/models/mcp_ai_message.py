# -*- coding: utf-8 -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class MCPAIMessage(models.Model):
    _name = "mcp.ai.message"
    _description = "MCP AI Conversation Message Record"
    _order = "sequence asc, id asc"

    conversation_id = fields.Many2one("mcp.ai.conversation", string="Conversation", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Sequence", default=10)
    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool Execution')
    ], string="Role", required=True, default='user')

    content = fields.Text(string="Message Content", required=True)
    seq_id = fields.Integer(string="Chunk Sequence ID", default=0)
    context_snapshot = fields.Text(string="Context Snapshot JSON")
    block_type = fields.Selection([
        ('markdown', 'Markdown Text'),
        ('tool_card', 'Tool Card'),
        ('approval_card', 'Approval Card'),
        ('error', 'Error Alert')
    ], string="Block Type", default='markdown', required=True)
