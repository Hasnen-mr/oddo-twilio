# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class MCPPromptBuilder(models.AbstractModel):
    _name = "mcp.ai.prompt.builder"
    _description = "System Prompt & Context Normalizer"

    @api.model
    def build_system_prompt(self, conversation, active_context=None):
        """Aggregates System Directives and Global User/Company Information into system prompt string."""
        prompt_parts = [
            "You are the official AI Assistant inside Odoo 18.",
            "You help users manage ERP workflows, query records, execute tools safely, and analyze data.",
            f"User: {self.env.user.name} (ID: {self.env.user.id}) | Company: {self.env.company.name} (ID: {self.env.company.id})"
        ]

        prompt_parts.append("\n=== INSTRUCTIONS ===")
        prompt_parts.append("Use available Odoo MCP tools to query or mutate Odoo records whenever requested by the user.")
        prompt_parts.append("Always return clean, concise markdown responses.")

        return "\n".join(prompt_parts)

    @api.model
    def get_available_tools(self, conversation=None, user_prompt="", active_context=None, allowed_tools=None):
        """Fetches optimized active tools using mcp.tool.selector router."""
        effective_prompt = (user_prompt or "").strip()
        if not effective_prompt and conversation:
            conv_service = self.env["mcp.ai.conversation.service"]
            history = conv_service.get_history(conversation.id)
            for m in reversed(history):
                if m.get("role") == "user" and m.get("content"):
                    effective_prompt = m.get("content", "").strip()
                    break

        tool_selector = self.env["mcp.tool.selector"]
        raw_tools = tool_selector.select_tools(
            conversation=conversation,
            user_prompt=effective_prompt,
            active_context=active_context,
            allowed_tools=allowed_tools
        )
        formatted_tools = []
        for t in raw_tools:
            name = t.get("name")
            desc = t.get("description", "Odoo MCP Tool")
            schema = t.get("inputSchema") or {"type": "object", "properties": {}}
            
            # Format inputSchema to match standard 'input_schema' specification
            formatted_tools.append({
                "name": name,
                "description": desc,
                "input_schema": schema,
                "category": t.get("category", "General")
            })
        return formatted_tools

    @api.model
    def build_payload(self, conversation, user_prompt="", active_context=None, allowed_tools=None):
        """Assembles full LLM input payload including system prompt, optimized tools, and message history."""
        system_prompt = self.build_system_prompt(conversation, active_context)
        conv_service = self.env["mcp.ai.conversation.service"]
        history = conv_service.get_history(conversation.id) if conversation else []

        messages = []
        for msg in history:
            if msg["role"] in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        effective_prompt = (user_prompt or "").strip()
        if not effective_prompt:
            for m in reversed(messages):
                if m.get("role") == "user" and m.get("content"):
                    effective_prompt = m.get("content", "").strip()
                    break

        if user_prompt and (not messages or messages[-1].get("content") != user_prompt):
            messages.append({"role": "user", "content": user_prompt})

        tools = self.get_available_tools(
            conversation=conversation,
            user_prompt=effective_prompt,
            active_context=active_context,
            allowed_tools=allowed_tools
        )

        return {
            "system": system_prompt,
            "messages": messages,
            "tools": tools,
            "max_tokens": 1024,
            "temperature": 0.3,
        }
