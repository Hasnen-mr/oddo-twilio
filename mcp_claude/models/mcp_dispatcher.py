# -*- coding: utf-8 -*-
"""
mcp.dispatcher Service (AbstractModel)
Routes incoming JSON-RPC 2.0 requests (initialize, ping, tools/*, resources/*, prompts/*)
to their corresponding capability handlers.
Idiomatic Odoo AbstractModel service pattern.
"""

import logging
from odoo import models, api
from ..utils.jsonrpc import parse_jsonrpc_request, format_jsonrpc_success, format_jsonrpc_error

_logger = logging.getLogger(__name__)

class MCPDispatcher(models.AbstractModel):
    _name = 'mcp.dispatcher'
    _description = 'MCP JSON-RPC 2.0 Protocol Dispatcher'

    @api.model
    def dispatch(self, raw_payload):
        """
        Main entrypoint for JSON-RPC 2.0 dispatching.
        Parses raw payload, routes to method handler, and returns formatted JSON-RPC 2.0 response.
        """
        parsed = parse_jsonrpc_request(raw_payload)
        if not parsed["valid"]:
            return format_jsonrpc_error(parsed.get("id"), -32700, parsed.get("error", "Parse error"))

        req_id = parsed["id"]
        method = parsed["method"]
        params = parsed["params"]

        # Protocol Lifecyle & Handshake Methods
        if method == "initialize":
            return format_jsonrpc_success(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": True, "listChanged": True},
                    "prompts": {"listChanged": True},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "Odoo Enterprise MCP Server",
                    "version": "18.0.1.0.3"
                }
            })

        if method == "notifications/initialized":
            return None  # Notification response

        if method == "ping":
            return format_jsonrpc_success(req_id, {})

        # Tools Capabilities
        if method == "tools/list":
            tool_handler = self.env['mcp.tool.handler'].sudo()
            res = tool_handler.handle_tools_list(params)
            return format_jsonrpc_success(req_id, res)

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not tool_name:
                return format_jsonrpc_error(req_id, -32602, "Invalid params: Missing tool 'name'")
            
            tool_handler = self.env['mcp.tool.handler'].sudo()
            res = tool_handler.handle_tools_call(tool_name, arguments)
            return format_jsonrpc_success(req_id, res)

        # Resources & Prompts Extensible Stubs
        if method in ("resources/list", "resources/templates/list"):
            return format_jsonrpc_success(req_id, {"resources": []})

        if method == "resources/read":
            return format_jsonrpc_error(req_id, -32602, "Resource URI not found.")

        if method == "prompts/list":
            return format_jsonrpc_success(req_id, {"prompts": []})

        if method == "prompts/get":
            return format_jsonrpc_error(req_id, -32602, "Prompt template not found.")

        # Method Not Found Fallback
        _logger.warning(f"Unhandled MCP JSON-RPC method requested: {method}")
        return format_jsonrpc_error(req_id, -32601, f"Method '{method}' not found")
