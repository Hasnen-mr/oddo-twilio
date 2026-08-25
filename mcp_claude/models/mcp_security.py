# -*- coding: utf-8 -*-
"""
mcp.security Service (AbstractModel)
Single source of truth for authentication, secret management, API keys,
OAuth token validation, and rate limiting integration.
Idiomatic Odoo AbstractModel service pattern.
"""

import logging
from odoo import models, fields, api
from ..utils.crypto import generate_random_secret
from ..services.rate_limiter import RateLimiter

_logger = logging.getLogger(__name__)

class MCPSecurityService(models.AbstractModel):
    _name = 'mcp.security'
    _description = 'MCP Security & Authentication Service'

    @api.model
    def get_hmac_secret(self) -> str:
        """Fetch installation-specific HMAC secret, generating one if missing."""
        config_param = self.env['ir.config_parameter'].sudo()
        secret = config_param.get_param('mcp_claude.hmac_secret')
        if not secret:
            secret = generate_random_secret(32)
            config_param.set_param('mcp_claude.hmac_secret', secret)
        return secret

    @api.model
    def validate_api_key(self, raw_token=None, auth_header=None, req=None):
        """
        Validate incoming bearer token or API key against database.
        Includes rate-limiting checks and audit timestamps.
        Returns (is_valid: bool, message: str, user_id: int).
        """
        req = req or (self.env.get('request') if hasattr(self.env, 'get') else None)
        ip_addr = "127.0.0.1"

        if req and hasattr(req, 'httprequest') and req.httprequest:
            httpreq = req.httprequest
            ip_addr = httpreq.headers.get('X-Real-IP') or \
                      httpreq.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                      httpreq.remote_addr or "127.0.0.1"

        if RateLimiter.is_ip_locked(ip_addr):
            return False, "Too many failed attempts. Temporary 15-minute lockout active.", None

        token = raw_token
        if not token and req and hasattr(req, 'httprequest') and req.httprequest:
            httpreq = req.httprequest
            auth_header = auth_header or httpreq.headers.get('Authorization')
            token = httpreq.args.get('token') or httpreq.args.get('api_key') or (httpreq.form.get('token') if hasattr(httpreq, 'form') else None)

        if not token and auth_header and str(auth_header).startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        if not token:
            RateLimiter.record_failed_attempt(ip_addr)
            return False, "Missing Authorization Bearer header or token parameter.", None

        token = str(token).strip()

        # Database API Key Search (Strict Complete Token HMAC Match Only)
        api_key_model = self.env['mcp.api.key'].sudo()
        token_hash = api_key_model.hash_token(token) if hasattr(api_key_model, 'hash_token') else None
        
        matched_key = None
        if token_hash:
            matched_key = api_key_model.search([('key_hash', '=', token_hash), ('active', '=', True)], limit=1)

        # Seamless backward-compatibility migration for pre-existing keys
        if not matched_key and token:
            legacy_secret = b"odoo_mcp_server_hmac_secret_key_v18"
            import hmac as _hmac, hashlib as _hashlib
            legacy_hash = _hmac.new(legacy_secret, token.encode('utf-8'), _hashlib.sha256).hexdigest()
            legacy_matched = api_key_model.search([('key_hash', '=', legacy_hash), ('active', '=', True)], limit=1)
            if legacy_matched and token_hash:
                legacy_matched.write({'key_hash': token_hash})
                matched_key = legacy_matched
                _logger.info("Migrated legacy API key #%s to installation-specific HMAC secret", legacy_matched.id)

        if matched_key:
            if not matched_key.user_id:
                RateLimiter.record_failed_attempt(ip_addr)
                return False, "API Key has no associated user.", None
            if matched_key.expires_at and matched_key.expires_at < fields.Datetime.now():
                RateLimiter.record_failed_attempt(ip_addr)
                return False, "API Key Expired", None
            matched_key.write({
                'last_used_at': fields.Datetime.now(),
                'last_used_ip': ip_addr
            })
            RateLimiter.reset_ip(ip_addr)
            return True, "Authorized via API Key", matched_key.user_id.id

        # Database OAuth Access Token Search (Strict Full Token Match Only)
        if token.startswith('mcp_access_'):
            oauth_token_rec = self.env['mcp.oauth.token'].sudo().search([
                ('access_token', '=', token),
                ('revoked', '=', False)
            ], limit=1)
            if oauth_token_rec:
                if not oauth_token_rec.user_id:
                    RateLimiter.record_failed_attempt(ip_addr)
                    return False, "OAuth token has no associated user.", None
                if oauth_token_rec.expires_at and oauth_token_rec.expires_at < fields.Datetime.now():
                    RateLimiter.record_failed_attempt(ip_addr)
                    return False, "OAuth Access Token Expired", None
                RateLimiter.reset_ip(ip_addr)
                return True, "Authorized via OAuth Access Token", oauth_token_rec.user_id.id

        RateLimiter.record_failed_attempt(ip_addr)
        return False, "Invalid API Key or Access Token", None
