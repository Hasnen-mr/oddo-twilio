# -*- coding: utf-8 -*-
from odoo import models, fields, api
import secrets
import datetime

class MCPOAuthCode(models.Model):
    _name = 'mcp.oauth.code'
    _description = 'MCP OAuth Authorization Code'

    code = fields.Char(string="Authorization Code", required=True, index=True, default=lambda self: secrets.token_urlsafe(32))
    client_id = fields.Many2one('mcp.oauth.client', string="Client App", required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string="User", required=True, ondelete='cascade')
    redirect_uri = fields.Char(string="Redirect URI", required=True)
    scope = fields.Char(string="Scope", default="mcp:read mcp:write")
    code_challenge = fields.Char(string="PKCE Code Challenge")
    code_challenge_method = fields.Char(string="PKCE Method", default="S256")
    expires_at = fields.Datetime(string="Expires At", required=True)
    used = fields.Boolean(string="Used / Consumed", default=False)

    @api.model
    def create_code(self, client_rec, user_rec, redirect_uri, scope="mcp:read mcp:write", code_challenge=None, code_challenge_method="S256"):
        expires = fields.Datetime.now() + datetime.timedelta(minutes=10)
        return self.create({
            'client_id': client_rec.id,
            'user_id': user_rec.id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method or "S256",
            'expires_at': expires,
            'used': False
        })
