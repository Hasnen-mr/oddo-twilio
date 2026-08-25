# -*- coding: utf-8 -*-
from odoo import models, fields

class MCPApprovalRequest(models.Model):
    _name = 'mcp.approval.request'
    _description = 'MCP Tool Approval Request'

    name = fields.Char(string="Request Reference", required=True, default="New Approval Request")
    tool_name = fields.Char(string="Tool Name", required=True)
    requested_by_user_id = fields.Many2one('res.users', string="Requested By", required=True, default=lambda self: self.env.user)
    arguments = fields.Text(string="Payload Arguments")
    state = fields.Selection([
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Status", default='pending', required=True)
    approved_by_id = fields.Many2one('res.users', string="Approved/Rejected By")
    approval_date = fields.Datetime(string="Action Date")

    def action_approve(self):
        for rec in self:
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now()
            })

    def action_reject(self):
        for rec in self:
            rec.write({
                'state': 'rejected',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now()
            })
