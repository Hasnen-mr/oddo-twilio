# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class MCPOAuthClient(models.Model):
    _name = "mcp.oauth.client"
    _description = "MCP OAuth Client Credentials"

    name = fields.Char("Client Name", required=True)
    client_id = fields.Char("Client ID", required=True, index=True, default=lambda self: self.env['mcp.api.key'].hash_token(str(fields.Datetime.now()))[:16])
    client_secret_encrypted = fields.Char("Encrypted Client Secret", required=True)
    client_type = fields.Selection([
        ('confidential', 'Confidential'),
        ('public', 'Public')
    ], string="Client Type", default='confidential')
    redirect_uri = fields.Char("Redirect URI")
    redirect_uris = fields.Text("Redirect URIs")
    active = fields.Boolean("Active", default=True)

    @api.model
    def create_oauth_client(self, name, redirect_uri=""):
        raw_secret = self.env['mcp.api.key'].hash_token(name + str(fields.Datetime.now()))[:32]
        enc_secret = base64.b64encode(raw_secret.encode('utf-8')).decode('utf-8')
        rec = self.create({
            "name": name,
            "client_secret_encrypted": enc_secret,
            "redirect_uri": redirect_uri,
            "redirect_uris": redirect_uri,
        })
        return raw_secret, rec.id

    def reveal_secret_admin(self):
        """Controlled Admin-only reveal action. Decrypts server-side and logs to audit log."""
        self.ensure_one()
        if not self.env.is_admin():
            raise UserError("Access Denied: Only administrators can reveal OAuth Client Secrets.")
        
        try:
            self.env['mcp.audit.log'].sudo().create({
                "tool_name": f"Admin Revealed OAuth Secret: {self.name}",
                "model_name": "mcp.oauth.client",
                "record_id": self.id,
                "action_type": "read",
                "status": "success",
                "user_id": self.env.user.id
            })
        except Exception as err:
            _logger.warning("Audit log creation exception in reveal_secret_admin: %s", err)

        try:
            raw_secret = base64.b64decode(self.client_secret_encrypted.encode('utf-8')).decode('utf-8')
            return raw_secret
        except Exception:
            return "Secret Decryption Error"
