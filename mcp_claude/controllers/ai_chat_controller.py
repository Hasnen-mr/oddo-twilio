# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class MCPAIChatController(http.Controller):

    @http.route('/mcp/ai/v1/chat/init', type='json', auth='user', methods=['POST'], csrf=False)
    def chat_init(self, session_id=None, scope=None, model_name=None, res_id=None, workspace_app=None, **kw):
        """Initializes or retrieves active conversation thread matching scope."""
        service = request.env['mcp.ai.conversation.service']
        res = service.get_or_create_conversation(
            session_id=session_id,
            scope=scope,
            model_name=model_name,
            res_id=res_id,
            workspace_app=workspace_app
        )
        history = service.get_history(res['conversation_id'])
        capabilities = request.env['mcp.ai.provider.claude'].get_capabilities()
        return {
            'success': True,
            'session_id': res['session_id'],
            'conversation_id': res['conversation_id'],
            'title': res['title'],
            'scope': res['scope'],
            'history': history,
            'capabilities': capabilities,
        }

    @http.route('/mcp/ai/v1/chat/message', type='json', auth='user', methods=['POST'], csrf=False)
    def chat_message(self, conversation_id, prompt, context_snapshot=None, **kw):
        """Phase 2 Endpoint: Processes user prompt and executes MCP tool decisions."""
        service = request.env['mcp.ai.conversation.service']
        conv = request.env['mcp.ai.conversation'].sudo().browse(conversation_id)
        if not conv.exists():
            return {'success': False, 'error': 'Conversation thread not found'}

        conv.write({'state': 'thinking'})
        try:
            res = service.process_user_prompt(conversation_id, prompt, context_snapshot=context_snapshot)
            conv.write({'state': 'completed'})
            return res
        except Exception as e:
            conv.write({'state': 'failed'})
            _logger.error(f"Error in chat_message processing: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @http.route('/mcp/ai/v1/chat/history', type='json', auth='user', methods=['POST'], csrf=False)
    def chat_history(self, conversation_id, limit=50, **kw):
        """Retrieves history for conversation."""
        service = request.env['mcp.ai.conversation.service']
        history = service.get_history(conversation_id, limit=limit)
        return {'success': True, 'history': history}
