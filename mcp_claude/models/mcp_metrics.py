# -*- coding: utf-8 -*-
from odoo import models, fields

class MCPMetrics(models.Model):
    _name = 'mcp.metrics'
    _description = 'MCP Server Metrics'

    timestamp = fields.Datetime(string="Timestamp", default=fields.Datetime.now, required=True)
    active_sessions = fields.Integer(string="Active Sessions", default=0)
    total_requests_24h = fields.Integer(string="Total Requests (24h)", default=0)
    error_count_24h = fields.Integer(string="Error Count (24h)", default=0)
    avg_latency_ms = fields.Float(string="Avg Latency (ms)", default=0.0)
