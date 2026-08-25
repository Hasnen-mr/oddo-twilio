# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPProviderBase(models.AbstractModel):
    _name = "mcp.ai.provider.base"
    _description = "Abstract Base LLM Provider"

    @api.model
    def get_capabilities(self):
        """Returns explicit capability flags dictionary for provider."""
        return {
            "supports_streaming": True,
            "supports_tool_calls": True,
            "supports_images": False,
            "supports_reasoning": False,
            "supports_json_output": True,
        }

    @api.model
    def generate_completion(self, payload):
        """Executes non-streaming completion call to LLM."""
        raise NotImplementedError("Subclasses must implement generate_completion")

    @api.model
    def generate_stream(self, payload, channel_name, conversation_id=None):
        """Executes streaming completion call to LLM, broadcasting chunks via bus.bus."""
        raise NotImplementedError("Subclasses must implement generate_stream")
