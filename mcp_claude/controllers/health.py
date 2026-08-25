# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import Response

_logger = logging.getLogger(__name__)

class MCPHealthController(http.Controller):
    @http.route('/mcp/health', type='http', auth='none', methods=['GET'], csrf=False)
    @http.route('/mcp/ping', type='http', auth='none', methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def health_check(self, **kwargs):
        _logger.info("MCP Health/Ping check requested")
        return Response(
            '{"status": "online", "message": "Odoo MCP Server is active and operational.", "version": "1.0.0"}',
            status=200,
            content_type='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )
