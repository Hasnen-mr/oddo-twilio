# -*- coding: utf-8 -*-
import logging
from odoo import models, api
from ..registry.tools import ToolRegistry

_logger = logging.getLogger(__name__)

class MCPToolSelector(models.AbstractModel):
    _name = "mcp.tool.selector"
    _description = "Context & Intent Driven MCP Tool Selection Router"

    @api.model
    def select_tools(self, conversation=None, user_prompt="", active_context=None, allowed_tools=None):
        """
        Dynamically selects a minimal, highly relevant subset of MCP tools based on exact
        tool-level metadata matching, context signals, and intent routing.
        """
        all_tools = ToolRegistry.get_all_tools(self.env)
        total_registered = len(all_tools)

        # 1. Explicit Allowed Tools Override (Absolute Hard Restriction)
        if allowed_tools is not None and isinstance(allowed_tools, (list, tuple, set)):
            allowed_set = {str(t).strip().lower() for t in allowed_tools}
            selected = [t for t in all_tools if t.get("name", "").lower() in allowed_set]
            self._log_instrumentation(total_registered, len(selected), "explicit allowed_tools constraint")
            return selected

        prompt_lower = (user_prompt or "").lower().strip()

        # 2. Focused Intent Overrides (Call Logs, Calling & Queue Creation)
        queue_keywords = ["queue", "auto dialer", "dialer queue", "auto-dialer"]
        calling_keywords = ["call", "dial", "phone call", "ring", "voice call"]
        call_log_keywords = ["call log", "call logs", "call history", "recent calls", "voice logs", "call record", "past calls"]

        is_call_log_intent = any(kw in prompt_lower for kw in call_log_keywords)
        is_queue_intent = any(kw in prompt_lower for kw in queue_keywords) and not is_call_log_intent
        is_calling_intent = any(kw in prompt_lower for kw in calling_keywords) and not is_queue_intent and not is_call_log_intent

        if is_call_log_intent:
            log_tool_names = {"odoo_search_twilio_call_log", "odoo_read_twilio_call_log"}
            selected = [t for t in all_tools if t.get("name") in log_tool_names]
            if not selected:
                selected = [t for t in all_tools if "call_log" in t.get("name", "")]
            self._log_instrumentation(total_registered, len(selected), "focused call-log intent")
            return selected

        if is_queue_intent:
            queue_tool_names = {"odoo_search_partners", "twilio_create_dialer_queue"}
            selected = [t for t in all_tools if t.get("name") in queue_tool_names]
            self._log_instrumentation(total_registered, len(selected), "focused queue intent")
            return selected

        if is_calling_intent:
            calling_tool_names = {"twilio_dial_contact", "odoo_search_partners", "odoo_get_contact"}
            selected = [t for t in all_tools if t.get("name") in calling_tool_names]
            self._log_instrumentation(total_registered, len(selected), "focused calling intent")
            return selected

        # 3. Tool-Level Metadata Intent Matching (Precision 1-5 Tool Output)
        selected_tool_names = set()

        # Contacts Entity Intent
        if any(kw in prompt_lower for kw in ["contact", "partner", "customer", "vendor", "people", "person", "client", "id"]):
            if any(kw in prompt_lower for kw in ["name", "who", "get", "details", "info", "read", "lookup"]):
                selected_tool_names.update(["odoo_get_contact", "odoo_search_partners"])
            elif any(kw in prompt_lower for kw in ["search", "show", "list", "find", "latest", "recent", "top", "view"]):
                selected_tool_names.add("odoo_search_partners")
            elif any(kw in prompt_lower for kw in ["create", "add", "new", "make"]):
                selected_tool_names.add("odoo_create_contact")

        # CRM Entity Intent
        if any(kw in prompt_lower for kw in ["crm", "lead", "opportunity", "pipeline", "deal", "stage"]):
            if any(kw in prompt_lower for kw in ["search", "show", "list", "find", "get", "latest", "recent", "top", "view"]):
                selected_tool_names.update(["odoo_search_leads", "odoo_search_opportunities"])
            elif any(kw in prompt_lower for kw in ["create", "add", "new", "make"]):
                selected_tool_names.add("odoo_create_lead")

        # Sales Entity Intent
        if any(kw in prompt_lower for kw in ["sale", "quotation", "order", "quote"]):
            if any(kw in prompt_lower for kw in ["search", "show", "list", "find", "get", "latest", "recent", "top", "view"]):
                selected_tool_names.update(["odoo_search_quotations", "odoo_search_orders"])
            elif any(kw in prompt_lower for kw in ["create", "add", "new", "make"]):
                selected_tool_names.add("odoo_create_quotation")

        # Inventory Entity Intent
        if any(kw in prompt_lower for kw in ["product", "stock", "inventory", "warehouse", "quant"]):
            if any(kw in prompt_lower for kw in ["search", "show", "list", "find", "get", "latest", "recent", "top", "view"]):
                selected_tool_names.add("odoo_search_products")
            elif any(kw in prompt_lower for kw in ["create", "add", "new", "make"]):
                selected_tool_names.add("odoo_create_product")

        # Accounting Entity Intent
        if any(kw in prompt_lower for kw in ["invoice", "bill", "payment", "account"]):
            if any(kw in prompt_lower for kw in ["search", "show", "list", "find", "get", "latest", "recent", "top", "view"]):
                selected_tool_names.update(["odoo_search_invoices", "odoo_search_vendor_bills"])
            elif any(kw in prompt_lower for kw in ["create", "add", "new", "make"]):
                selected_tool_names.add("odoo_create_invoice")

        # Explicit Technical ORM Intent (Only included if explicitly requested)
        if any(kw in prompt_lower for kw in ["technical", "orm", "read record", "explain record", "aggregate"]):
            selected_tool_names.update(["odoo_read_record", "odoo_explain_record", "odoo_aggregate"])

        if selected_tool_names:
            selected = [t for t in all_tools if t.get("name") in selected_tool_names]
            self._log_instrumentation(total_registered, len(selected), f"precise tool metadata match: {list(selected_tool_names)}")
            return selected

        # 4. Small Bounded Fallback (Max 4 Search Tools)
        fallback_tool_names = {
            "odoo_search_partners", "odoo_search_leads",
            "odoo_search_orders", "odoo_search_products"
        }
        selected = [t for t in all_tools if t.get("name") in fallback_tool_names]
        self._log_instrumentation(total_registered, len(selected), "bounded fallback strategy")
        return selected

    @api.model
    def _log_instrumentation(self, total_registered, selected_count, trigger_reason):
        """Logs sanitized, non-sensitive tool selection instrumentation statistics."""
        reduction_pct = round((1.0 - (selected_count / max(total_registered, 1))) * 100, 1)
        est_tokens_saved = (total_registered - selected_count) * 80
        _logger.info(
            f"[Tool Selector] Optimization: Registered={total_registered}, Selected={selected_count}, "
            f"Reduction={reduction_pct}%, Est Tokens Saved=~{est_tokens_saved} ({trigger_reason})"
        )
