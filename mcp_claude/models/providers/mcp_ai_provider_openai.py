# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPProviderOpenAI(models.AbstractModel):
    _inherit = "mcp.ai.provider.base"
    _name = "mcp.ai.provider.openai"
    _description = "OpenAI GPT-4o LLM Provider Subclass"

    @api.model
    def get_capabilities(self):
        caps = super().get_capabilities()
        caps.update({
            "provider_name": "OpenAI (GPT-4o / GPT-4o-mini)",
            "supports_reasoning": True,
            "supports_tool_calls": True,
            "supports_images": True,
        })
        return caps

    @api.model
    def format_tools_for_openai(self, raw_tools):
        """Helper to convert MCP tools into OpenAI function declaration format."""
        formatted_tools = []
        if not raw_tools:
            return formatted_tools
        for t in raw_tools:
            if isinstance(t, dict) and t.get("type") == "function":
                formatted_tools.append(t)
            elif isinstance(t, dict):
                name = t.get("name")
                desc = t.get("description", "")
                params = t.get("input_schema") or t.get("inputSchema") or t.get("parameters") or {"type": "object", "properties": {}}
                if name:
                    formatted_tools.append({
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": desc,
                            "parameters": params
                        }
                    })
        return formatted_tools

    @api.model
    def generate_completion(self, payload):
        """Phase 2 OpenAI API completion provider using mcp.server.config single source of truth."""
        config_model = self.env['mcp.server.config']
        api_key = config_model.get_openai_api_key()
        model_name = config_model.get_openai_model()

        # If no API key configured, return explicit user-safe configuration message
        if not api_key:
            _logger.info("OpenAI API call skipped: No valid API key configured in system configuration.")
            return {
                "type": "text",
                "content": "OpenAI API is not configured.\nAn administrator can add the OpenAI API key from MCP Claude -> Configuration -> Server Configuration -> OpenAI API Configuration."
            }

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Build messages payload
        messages = []
        if payload.get("system"):
            messages.append({"role": "system", "content": payload.get("system")})

        raw_msgs = payload.get("messages", [])
        for m in raw_msgs:
            if isinstance(m, dict):
                messages.append(m)

        # Convert tool format to OpenAI function schema
        tools_param = self.format_tools_for_openai(payload.get("tools", []))

        body = {
            "model": model_name or "gpt-4o",
            "messages": messages,
            "max_tokens": payload.get("max_tokens", 1024),
        }
        if tools_param:
            body["tools"] = tools_param
            body["tool_choice"] = "auto"

        try:
            _logger.info(f"Sending OpenAI API request (Model: {body['model']}, {len(messages)} messages, {len(tools_param or [])} tools)")
            resp = requests.post(url, headers=headers, json=body, timeout=35)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    return {"type": "text", "content": "OpenAI returned an empty response."}

                first_choice = choices[0]
                finish_reason = first_choice.get("finish_reason")
                msg = first_choice.get("message", {})

                # Check if OpenAI returned tool calls
                raw_tool_calls = msg.get("tool_calls", [])
                if raw_tool_calls or finish_reason == "tool_calls":
                    parsed_tool_calls = []
                    for tc in raw_tool_calls:
                        tc_id = tc.get("id")
                        func = tc.get("function", {})
                        fn_name = func.get("name")
                        fn_args_raw = func.get("arguments", "{}")
                        try:
                            fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else (fn_args_raw or {})
                        except Exception:
                            fn_args = {}

                        if fn_name:
                            parsed_tool_calls.append({
                                "id": tc_id,
                                "name": fn_name,
                                "input": fn_args
                            })

                    if parsed_tool_calls:
                        return {
                            "type": "tool_use",
                            "tool_calls": parsed_tool_calls,
                            "text": msg.get("content") or "",
                            "raw_response": data
                        }

                text_content = msg.get("content", "")
                return {
                    "type": "text",
                    "content": text_content or "Response complete."
                }

            # Parse exact OpenAI error message
            err_msg = ""
            try:
                err_data = resp.json()
                if isinstance(err_data, dict) and "error" in err_data:
                    err_msg = err_data["error"].get("message", "")
            except Exception:
                err_msg = resp.text[:200]

            _logger.error(f"OpenAI API error status {resp.status_code}: {resp.text}")
            detail = f": {err_msg}" if err_msg else ""
            return {
                "type": "text",
                "content": f"OpenAI API Error ({resp.status_code}){detail}"
            }

        except Exception as e:
            _logger.error(f"Failed to communicate with OpenAI API: {e}")
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
