# -*- coding: utf-8 -*-
from odoo import models, fields

class MCPAuditLog(models.Model):
    _name = 'mcp.audit.log'
    _description = 'MCP Audit Log'

    timestamp = fields.Datetime(string="Timestamp", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string="User", required=True)
    tool_name = fields.Char(string="Tool Name")
    model_name = fields.Char(string="Target Model")
    action_type = fields.Char(string="Action Type")
    request_payload = fields.Text(string="Request Payload")
    response_summary = fields.Text(string="Response Summary")
    error_message = fields.Text(string="Error Message")
    execution_time_ms = fields.Float(string="Execution Time (ms)")
    record_id = fields.Integer(string="Record ID")
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('denied', 'Denied')
    ], string="Status", default='success', required=True)
