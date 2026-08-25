# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPProviderClaude(models.AbstractModel):
    _inherit = "mcp.ai.provider.base"
    _name = "mcp.ai.provider.claude"
    _description = "Anthropic Claude LLM Provider Subclass"

    @api.model
    def get_capabilities(self):
        caps = super().get_capabilities()
        caps.update({
            "provider_name": "Anthropic Claude 3.5 Sonnet",
            "supports_reasoning": True,
            "supports_tool_calls": True,
        })
        return caps

    @api.model
    def generate_completion(self, payload):
        """Phase 2 Claude API completion provider using mcp.server.config single source of truth."""
        api_key = self.env['mcp.server.config'].get_claude_api_key()

        # If no API key configured, return explicit user-safe configuration message
        if not api_key or api_key == "mcp_live_default":
            _logger.info("Claude API call skipped: No valid API key configured in system configuration.")
            return {
                "type": "text",
                "content": "Claude API is not configured.\nAn administrator can add the Anthropic API key from MCP Claude -> Configuration -> Server Configuration."
            }

        url = "https://api.anthropic.com/v1/messages"
        # Secure headers - API key is never logged or returned to client
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": payload.get("max_tokens", 1024),
            "system": payload.get("system", ""),
            "messages": payload.get("messages", [])
        }

        if payload.get("tools"):
            body["tools"] = payload.get("tools")

        try:
            _logger.info(f"Sending Anthropic API request ({len(body.get('messages', []))} messages, {len(body.get('tools', []))} tools)")
            resp = requests.post(url, headers=headers, json=body, timeout=35)
            
            if resp.status_code == 200:
                data = resp.json()
                stop_reason = data.get("stop_reason")
                content_blocks = data.get("content", [])

                tool_calls = []
                text_response = ""

                for block in content_blocks:
                    if block.get("type") == "text":
                        text_response += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "name": block.get("name"),
                            "input": block.get("input", {})
                        })

                if stop_reason == "tool_use" and tool_calls:
                    return {
                        "type": "tool_use",
                        "tool_calls": tool_calls,
                        "text": text_response,
                        "raw_response": data
                    }

                return {
                    "type": "text",
                    "content": text_response or "Response complete."
                }

            err_msg = ""
            try:
                err_data = resp.json()
                if isinstance(err_data, dict) and "error" in err_data:
                    err_msg = err_data["error"].get("message", "")
            except Exception:
                err_msg = resp.text[:200]

            _logger.error(f"Claude API error status {resp.status_code}: {resp.text}")
            display_err = f"API Response Error ({resp.status_code}): {err_msg}" if err_msg else f"API Response Error ({resp.status_code}): Unable to complete request."
            return {
                "type": "text",
                "content": display_err
            }
        except Exception as e:
            _logger.error(f"Failed to communicate with Anthropic API: {e}")
            return {
                "type": "text",
                "content": f"Communication Error: {str(e)}"
            }

    @api.model
    def generate_stream(self, payload, channel_name, conversation_id=None):
        """Streams completion chunks via bus.bus."""
        res = self.generate_completion(payload)
        text = res.get("content", "") if isinstance(res, dict) else str(res)
        conv_service = self.env["mcp.ai.conversation.service"]
        
        # Stream chunks to bus
        chunk_size = 25
        seq = 1
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            self.env['bus.bus']._sendone(channel_name, 'mcp_ai_chunk', {
                'conversation_id': conversation_id,
                'seq_id': seq,
                'chunk': chunk,
                'done': False
            })
            seq += 1

        self.env['bus.bus']._sendone(channel_name, 'mcp_ai_chunk', {
            'conversation_id': conversation_id,
            'seq_id': seq,
            'chunk': '',
            'done': True
        })

        if conversation_id:
            conv_service.add_message(conversation_id, 'assistant', text, seq_id=seq)

        return text
