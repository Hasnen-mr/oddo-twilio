# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPProviderManager(models.AbstractModel):
    _name = "mcp.ai.provider.manager"
    _description = "LLM Provider Routing & Dispatch Manager"

    @api.model
    def get_active_provider(self):
        """Returns the active LLM provider model instance based on mcp.server.config setting."""
        config = self.env["mcp.server.config"].sudo().search([], limit=1)
        provider_type = config.ai_provider if (config and config.ai_provider) else "claude"

        if provider_type == "openai":
            return self.env["mcp.ai.provider.openai"]
        elif provider_type == "ollama":
            if "mcp.ai.provider.ollama" in self.env:
                return self.env["mcp.ai.provider.ollama"]
            return self.env["mcp.ai.provider.claude"]
        else:
            return self.env["mcp.ai.provider.claude"]
