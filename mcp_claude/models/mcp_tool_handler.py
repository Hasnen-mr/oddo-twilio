# -*- coding: utf-8 -*-
"""
mcp.tool.handler Service (AbstractModel)
Handles tools/list and tools/call JSON-RPC 2.0 protocol methods.
Can be extended via standard Odoo model inheritance (_inherit).
"""

import json
import logging
from odoo import models, api
from ..registry.tools import ToolRegistry

_logger = logging.getLogger(__name__)

class MCPToolHandler(models.AbstractModel):
    _name = 'mcp.tool.handler'
    _description = 'MCP Tool Capability Handler'

    @api.model
    def handle_tools_list(self, params=None):
        """Handle tools/list request by delegating to ToolRegistry."""
        registered_tools = ToolRegistry.get_all_tools(self.env)
        tools_list = []
        for t in registered_tools:
            tools_list.append({
                "name": t["name"],
                "description": t.get("description", "Odoo MCP Tool"),
                "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}})
            })
        return {"tools": tools_list}

    @api.model
    def handle_tools_call(self, name, arguments=None, context=None):
        """Handle tools/call request by delegating to ToolRegistry execution engine."""
        arguments = arguments or {}
        try:
            res = ToolRegistry.execute_tool(self.env, name, arguments)
            return {
                "content": [
                    {"type": "text", "text": json.dumps(res, indent=2, default=str)}
                ],
                "isError": not res.get("success", True) if isinstance(res, dict) else False
            }
        except Exception as e:
            _logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            return {
                "isError": True,
                "content": [
                    {"type": "text", "text": f"Execution error: {e}"}
                ]
            }
