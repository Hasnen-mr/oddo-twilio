# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api
from ..registry.tools import ToolRegistry

_logger = logging.getLogger(__name__)

class MCPConversationService(models.AbstractModel):
    _name = "mcp.ai.conversation.service"
    _description = "Conversation Management & Hybrid Scope Orchestration Service"

    @api.model
    def create_session(self, user_id=None, device_info=None):
        """Creates a new user AI session record."""
        target_user = user_id or self.env.user.id
        session = self.env["mcp.ai.session"].sudo().create({
            "name": f"Session {fields.Date.today()}",
            "user_id": target_user,
            "company_id": self.env.company.id,
            "device_info": device_info or "WebClient Browser",
            "schema_version": 2,
        })
        return session.id

    @api.model
    def get_or_create_conversation(self, session_id=None, scope=None, model_name=None, res_id=None, workspace_app=None):
        """Finds active conversation matching the scope context hierarchy or initializes a new thread."""
        user = self.env.user
        domain = [("user_id", "=", user.id), ("active", "=", True)]
        if session_id:
            domain.append(("id", "=", session_id))
        
        session = self.env["mcp.ai.session"].sudo().search(domain, limit=1)
        if not session:
            session_id = self.create_session(user_id=user.id)
            session = self.env["mcp.ai.session"].sudo().browse(session_id)

        # Enforce Global Scope Baseline
        scope = "global"
        conv_domain = [("session_id", "=", session.id), ("scope", "=", scope)]
        conversation = self.env["mcp.ai.conversation"].sudo().search(conv_domain, order="id desc", limit=1)
        
        if not conversation:
            title = "Global AI Assistant"
            conversation = self.env["mcp.ai.conversation"].sudo().create({
                "name": title,
                "session_id": session.id,
                "user_id": user.id,
                "company_id": self.env.company.id,
                "scope": "global",
                "current_model": False,
                "current_res_id": False,
                "workspace_app": False,
                "state": "idle",
                "schema_version": 2,
            })

        return {
            "session_id": session.id,
            "conversation_id": conversation.id,
            "title": conversation.name,
            "scope": conversation.scope,
            "current_model": conversation.current_model,
            "current_res_id": conversation.current_res_id,
            "workspace_app": conversation.workspace_app,
            "state": conversation.state,
        }

    @api.model
    def add_message(self, conversation_id, role, content, context_snapshot=None, seq_id=0, block_type="markdown"):
        """Appends a new persistent message record to the conversation."""
        conv = self.env["mcp.ai.conversation"].sudo().browse(conversation_id)
        if not conv.exists():
            return False

        snapshot_str = json.dumps(context_snapshot) if isinstance(context_snapshot, dict) else context_snapshot
        msg = self.env["mcp.ai.message"].sudo().create({
            "conversation_id": conv.id,
            "role": role,
            "content": content,
            "seq_id": seq_id,
            "context_snapshot": snapshot_str or False,
            "block_type": block_type,
        })
        return {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "seq_id": msg.seq_id,
            "block_type": msg.block_type,
        }

    @api.model
    def get_history(self, conversation_id, limit=50):
        """Returns ordered message history formatted for LLM consumption."""
        conv = self.env["mcp.ai.conversation"].sudo().browse(conversation_id)
        if not conv.exists():
            return []

        messages = self.env["mcp.ai.message"].sudo().search(
            [("conversation_id", "=", conv.id)],
            order="sequence asc, id asc",
            limit=limit
        )
        return [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "block_type": m.block_type,
            "seq_id": m.seq_id,
        } for m in messages]

    @api.model
    def process_user_prompt(self, conversation_id, user_prompt, context_snapshot=None):
        """Phase 2 Orchestrator: Receives user prompt, executes Claude API tool decisions, and returns final response."""
        conv = self.env["mcp.ai.conversation"].sudo().browse(conversation_id)
        if not conv.exists():
            return {"success": False, "error": f"Conversation #{conversation_id} not found."}

        # 1. Add user message to persistent history
        self.add_message(conversation_id, "user", user_prompt, context_snapshot=context_snapshot)

        # 2. Build initial LLM payload with tools & system prompt
        prompt_builder = self.env["mcp.ai.prompt.builder"]
        provider = self.env["mcp.ai.provider.manager"].get_active_provider()

        payload = prompt_builder.build_payload(conv, user_prompt=user_prompt, active_context=context_snapshot)

        # 3. Call Active LLM Provider (Claude or OpenAI)
        response = provider.generate_completion(payload)

        # 4. Handle Tool Calling Loop if Claude requested a tool execution
        if isinstance(response, dict) and response.get("type") == "tool_use":
            tool_calls = response.get("tool_calls", [])
            tool_results = []

            for call in tool_calls:
                tool_name = call.get("name")
                tool_args = call.get("input", {})
                _logger.info(f"[Phase 2 Agent] Executing tool '{tool_name}' with args: {tool_args}")
                
                # Execute tool via ToolRegistry
                t_res = ToolRegistry.execute_tool(self.env, tool_name, tool_args)
                tool_results.append({
                    "tool": tool_name,
                    "result": t_res
                })

            # Format tool observations for follow-up synthesis call
            followup_prompt = f"Tool Execution Results:\n{json.dumps(tool_results, indent=2, default=str)}\n\nPlease synthesize a clear, helpful response for the user based on these results."
            
            # Save intermediate tool execution note to assistant history
            tool_summary_text = f"Executed tool `{tool_calls[0].get('name')}`"
            
            payload_followup = prompt_builder.build_payload(conv, user_prompt=followup_prompt, active_context=context_snapshot)
            final_res = provider.generate_completion(payload_followup)
            
            final_text = final_res.get("content", "Task complete.") if isinstance(final_res, dict) else str(final_res)
            
            # Add final response to conversation history
            msg_rec = self.add_message(conversation_id, "assistant", final_text)
            return {
                "success": True,
                "conversation_id": conversation_id,
                "response_block": msg_rec,
                "tool_executions": tool_results
            }

        # Standard text response without tool call
        final_text = response.get("content", "") if isinstance(response, dict) else str(response)
        msg_rec = self.add_message(conversation_id, "assistant", final_text)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "response_block": msg_rec
        }
