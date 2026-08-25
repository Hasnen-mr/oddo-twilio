# -*- coding: utf-8 -*-
from odoo import models, fields

class MCPOAuthToken(models.Model):
    _name = 'mcp.oauth.token'
    _description = 'MCP OAuth Token'

    access_token = fields.Char(string="Access Token", required=True, index=True)
    refresh_token = fields.Char(string="Refresh Token", index=True)
    client_id = fields.Many2one('mcp.oauth.client', string="Client App", required=True)
    user_id = fields.Many2one('res.users', string="User", required=True)
    code_challenge = fields.Char(string="PKCE Code Challenge")
    code_challenge_method = fields.Char(string="PKCE Method", default="S256")
    expires_at = fields.Datetime(string="Expires At", required=True)
    revoked = fields.Boolean(string="Revoked", default=False)
