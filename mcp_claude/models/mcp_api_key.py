# -*- coding: utf-8 -*-
import secrets
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class MCPApiKey(models.Model):
    _name = "mcp.api.key"
    _description = "MCP Security API Key & Opaque Token"

    name = fields.Char("Token Name", required=True, default="Claude Desktop")
    key_prefix = fields.Char("Key Prefix (Short ID)", index=True)
    key_hash = fields.Char("HMAC-SHA256 Hash", required=True, index=True)
    user_id = fields.Many2one("res.users", "Owner", required=True, default=lambda self: self.env.user)
    active = fields.Boolean("Active", default=True)
    scopes = fields.Selection([
        ('full', 'Full Access (Read/Write)'),
        ('read_only', 'Read Only'),
        ('tools_only', 'Tools Only Execution')
    ], string="Permission Scope", default='full')
    allowed_ips = fields.Char("Allowed IPs (Comma separated)", help="Optional IP whitelist")
    expiration_policy = fields.Selection([
        ('never', 'Never Expire'),
        ('30_days', '30 Days'),
        ('90_days', '90 Days'),
        ('custom', 'Custom Date')
    ], string="Expiration Policy", default='never')
    expires_at = fields.Datetime("Expires At")
    last_used_at = fields.Datetime("Last Used At")
    last_used_ip = fields.Char("Last Used IP")

    @api.model
    def hash_token(self, token_str: str) -> str:
        """Computes HMAC-SHA256 hash of token using installation-specific server secret."""
        secret = self.env['mcp.security'].get_hmac_secret()
        secret_bytes = secret.encode('utf-8') if isinstance(secret, str) else secret
        return hmac.new(secret_bytes, str(token_str).encode('utf-8'), hashlib.sha256).hexdigest()

    @api.model
    def generate_opaque_connector_token(self, name="Claude Desktop", scopes="full", expiration_policy="never", allowed_ips=None, user_id=None):
        """
        Generates high-entropy opaque random token (secrets.token_urlsafe(32)).
        Zero user info or prefix encoded into the raw token string.
        Persists HMAC-SHA256 hash in DB. Caches active token in system parameters.
        Returns raw token string ONCE to caller.
        """
        raw_token = secrets.token_urlsafe(32)  # Pure opaque random string
        prefix = raw_token[:8]
        token_hash = self.hash_token(raw_token)

        expires_dt = None
        if expiration_policy == '30_days':
            expires_dt = datetime.now() + timedelta(days=30)
        elif expiration_policy == '90_days':
            expires_dt = datetime.now() + timedelta(days=90)

        target_uid = user_id or (self.env.user.id if self.env.user else self.env.uid) or 2

        record = self.create({
            "name": name,
            "key_prefix": prefix,
            "key_hash": token_hash,
            "user_id": target_uid,
            "active": True,
            "scopes": scopes,
            "allowed_ips": allowed_ips,
            "expiration_policy": expiration_policy,
            "expires_at": expires_dt,
        })
        
        # Log Audit Trail
        try:
            self.env['mcp.audit.log'].sudo().create({
                "tool_name": f"Generated Token: {name}",
                "model_name": "mcp.api.key",
                "action_type": "create",
                "status": "success",
                "user_id": target_uid
            })
        except Exception as err:
            _logger.warning("Audit log creation exception: %s", err)

        # Cache active token in ir.config_parameter for seamless retrieval in Claude Desktop configs
        try:
            ICPSudo = self.env['ir.config_parameter'].sudo()
            ICPSudo.set_param(f"mcp_claude.user_token_{target_uid}", raw_token)
            ICPSudo.set_param("mcp_claude.default_api_key", raw_token)
        except Exception as err:
            _logger.warning("Config parameter save exception: %s", err)

        return raw_token, record.id

    @api.model
    def get_or_create_user_api_key(self, user_id=None):
        """
        Fetches or provisions a valid, non-expired API key for the user to embed in Claude Desktop configurations.
        """
        uid = user_id or (self.env.user.id if self.env.user else self.env.uid) or 2
        ICPSudo = self.env['ir.config_parameter'].sudo()
        param_name = f"mcp_claude.user_token_{uid}"
        cached_token = ICPSudo.get_param(param_name)

        if cached_token:
            token_hash = self.hash_token(cached_token)
            valid_rec = self.sudo().search([
                ('key_hash', '=', token_hash),
                ('user_id', '=', uid),
                ('active', '=', True)
            ], limit=1)
            if valid_rec and (not valid_rec.expires_at or valid_rec.expires_at > fields.Datetime.now()):
                return cached_token

        # Check default global token parameter
        default_param_token = ICPSudo.get_param("mcp_claude.default_api_key")
        if default_param_token and default_param_token != "mcp_live_default":
            token_hash = self.hash_token(default_param_token)
            valid_rec = self.sudo().search([
                ('key_hash', '=', token_hash),
                ('active', '=', True)
            ], limit=1)
            if valid_rec and (not valid_rec.expires_at or valid_rec.expires_at > fields.Datetime.now()):
                ICPSudo.set_param(param_name, default_param_token)
                return default_param_token

        # Generate a new dedicated token for Claude Desktop
        raw_token, _rec_id = self.sudo().generate_opaque_connector_token(
            name="Claude Desktop Key",
            scopes="full",
            expiration_policy="never",
            user_id=uid
        )
        return raw_token

    def action_revoke(self):
        """Revokes token and immediately terminates all linked active sessions."""
        user_ids = self.mapped('user_id.id')
        if user_ids:
            sessions = self.env['mcp.session'].sudo().search([('user_id', 'in', user_ids), ('active', '=', True)])
            sessions.write({'active': False, 'status': 'disconnected'})

        for rec in self:
            rec.active = False
            # Audit Log
            try:
                self.env['mcp.audit.log'].sudo().create({
                    "tool_name": f"Revoked Token: {rec.name}",
                    "model_name": "mcp.api.key",
                    "record_id": rec.id,
                    "action_type": "delete",
                    "status": "success",
                    "user_id": self.env.user.id if self.env.user else self.env.uid
                })
            except Exception as err:
                _logger.warning("Audit log creation exception in action_revoke: %s", err)

        return True

    @api.model
    def action_revoke_all_user_tokens(self, user_id=None):
        """Emergency admin action to revoke all tokens for a user."""
        target_uid = user_id or self.env.user.id
        keys = self.search([('user_id', '=', target_uid), ('active', '=', True)])
        keys.action_revoke()
        return True
