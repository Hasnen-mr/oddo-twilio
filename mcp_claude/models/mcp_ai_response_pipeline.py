# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPResponsePipeline(models.AbstractModel):
    _name = "mcp.ai.response.pipeline"
    _description = "LLM Output Normalizer & Block Generator"

    @api.model
    def normalize_response(self, raw_output):
        """Converts raw LLM response into structured, typed UI content blocks."""
        if not raw_output:
            return {"block_type": "markdown", "content": ""}

        if isinstance(raw_output, dict):
            if "error" in raw_output:
                return {
                    "block_type": "error",
                    "content": raw_output.get("error"),
                    "title": "AI Service Alert"
                }
            if "tool_call" in raw_output:
                return {
                    "block_type": "tool_card",
                    "content": raw_output.get("tool_call"),
                    "status": "pending"
                }

        # Default markdown text block
        text_content = str(raw_output).strip()
        return {
            "block_type": "markdown",
            "content": text_content
        }
