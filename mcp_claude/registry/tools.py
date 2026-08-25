# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, Any, List, Callable
from ..utils.model_inspector import ModelInspector

_logger = logging.getLogger(__name__)
_REGISTERED_TOOLS: Dict[str, Dict[str, Any]] = {}

def mcp_tool(name: str, version: str = "1.0.0", category: str = "General",
             description: str = "", risk_level: str = "Low",
             read_only: bool = True, requires_approval: bool = False, author: str = "Core",
             input_schema: Dict[str, Any] = None):
    def decorator(func: Callable):
        tool_meta = {
            "name": name,
            "version": version,
            "category": category,
            "description": description or func.__doc__ or "",
            "risk_level": risk_level,
            "read_only": read_only,
            "requires_approval": requires_approval,
            "author": author,
            "inputSchema": input_schema or {"type": "object", "properties": {}},
            "handler": func,
            "is_builtin": True
        }
        _REGISTERED_TOOLS[name] = tool_meta
        return func
    return decorator

class ToolRegistry:
    @classmethod
    def generate_input_schema(cls, operation: str, search_fields: list) -> dict:
        """Dynamically generate MCP inputSchema based on operation and configured fields."""
        if operation == "create":
            props = {}
            if search_fields:
                for sf in search_fields:
                    props[sf] = {"type": "string", "description": f"Value for {sf}"}
            return {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "object",
                        "properties": props,
                        "description": "Field values to create the record"
                    }
                },
                "required": ["values"]
            }
        elif operation == "write":
            props = {}
            if search_fields:
                for sf in search_fields:
                    props[sf] = {"type": "string", "description": f"Value for {sf}"}
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Target record ID"},
                    "values": {
                        "type": "object",
                        "properties": props,
                        "description": "Field values to update"
                    }
                },
                "required": ["id", "values"]
            }
        elif operation == "delete":
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Target record ID to delete"}
                },
                "required": ["id"]
            }
        elif operation == "explain":
            return {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Target Odoo model name"},
                    "id": {"type": "integer", "description": "Optional record ID"}
                },
                "required": ["model"]
            }
        elif operation == "read":
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Target record ID"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Optional fields list to read"}
                },
                "required": ["id"]
            }
        elif operation == "aggregate":
            return {
                "type": "object",
                "properties": {
                    "domain": {"type": "array", "description": "Search domain filters"},
                    "groupby": {"type": "array", "items": {"type": "string"}, "description": "Group by dimensions"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to aggregate"}
                }
            }
        else: # search
            props = {
                "limit": {"type": "integer", "default": 20, "description": "Max records to return (1-100)"},
                "offset": {"type": "integer", "default": 0, "description": "Pagination offset"}
            }
            if search_fields:
                for sf in search_fields:
                    props[sf] = {"type": "string", "description": f"Filter by {sf}"}
            return {
                "type": "object",
                "properties": props
            }

    @classmethod
    def get_all_tools(cls, env=None) -> List[Dict[str, Any]]:
        """Return unified list of built-in Python tools and active database custom tools."""
        tools_list = []
        # 1. Built-in Tools
        for name, tool_meta in _REGISTERED_TOOLS.items():
            tools_list.append({
                "id": f"builtin_{name}",
                "name": tool_meta["name"],
                "description": tool_meta.get("description", ""),
                "category": tool_meta.get("category", "General"),
                "inputSchema": tool_meta.get("inputSchema", {"type": "object", "properties": {}}),
                "is_builtin": True,
                "active": True
            })

        # 2. Database Custom Tools (if env provided)
        if env:
            try:
                db_tools = env['mcp.tool'].sudo().search([('active', '=', True)], order='sequence, id')
                builtin_names = {t["name"] for t in tools_list}
                for db_t in db_tools:
                    if db_t.name not in builtin_names:
                        s_fields = json.loads(db_t.search_fields) if db_t.search_fields else []
                        tools_list.append({
                            "id": db_t.id,
                            "name": db_t.name,
                            "display_name": db_t.display_name or db_t.name,
                            "description": db_t.description or f"{db_t.operation.capitalize()} {db_t.model_name}",
                            "model_name": db_t.model_name,
                            "operation": db_t.operation,
                            "search_fields": s_fields,
                            "result_fields": json.loads(db_t.result_fields) if db_t.result_fields else [],
                            "inputSchema": cls.generate_input_schema(db_t.operation, s_fields),
                            "is_builtin": False,
                            "active": db_t.active
                        })
            except Exception as e:
                _logger.warning(f"Failed fetching database custom tools: {e}")

        return tools_list

    @classmethod
    def get_tool(cls, env, name: str) -> Dict[str, Any]:
        if name in _REGISTERED_TOOLS:
            return _REGISTERED_TOOLS[name]

        if env:
            name_clean = (name or '').strip().lower()
            all_tools = cls.get_all_tools(env)
            for t in all_tools:
                if (t.get('name') or '').strip().lower() == name_clean:
                    return t

            db_t = env['mcp.tool'].sudo().with_context(active_test=False).search([('name', '=', name_clean)], limit=1)
            if db_t:
                s_fields = json.loads(db_t.search_fields) if db_t.search_fields else []
                r_fields = json.loads(db_t.result_fields) if db_t.result_fields else []
                return {
                    "id": db_t.id,
                    "name": db_t.name,
                    "display_name": db_t.display_name,
                    "description": db_t.description,
                    "model_name": db_t.model_name,
                    "operation": db_t.operation,
                    "search_fields": s_fields,
                    "result_fields": r_fields,
                    "inputSchema": cls.generate_input_schema(db_t.operation, s_fields),
                    "is_builtin": False,
                    "active": db_t.active
                }
        return None

    @classmethod
    def execute_tool(cls, env, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        name_clean = (name or '').strip().lower()
        if name_clean in ('ping', 'odoo_ping'):
            return {"status": "online", "message": "Odoo MCP Server is active and operational."}
        
        # 1. Check Built-in Tools
        if name in _REGISTERED_TOOLS:
            tool_meta = _REGISTERED_TOOLS[name]
            handler = tool_meta.get('handler')
            if not handler:
                return {"success": False, "error": {"code": "missing_handler", "message": f"Handler for '{name}' missing."}}
            try:
                return handler(env, params or {})
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                _logger.error(f"Error executing built-in tool '{name}': {e}\n{tb}")
                return {"success": False, "error": {"code": "execution_error", "message": str(e), "traceback": tb}}

        # 2. Check Database Custom Tools
        tool_meta = cls.get_tool(env, name)
        if not tool_meta:
            return {
                "success": False,
                "error": {
                    "code": "unknown_tool",
                    "message": f"MCP Tool '{name}' is not registered or is disabled."
                }
            }

        model_name = tool_meta.get("model_name")
        operation = tool_meta.get("operation")
        search_fields = tool_meta.get("search_fields", [])
        result_fields = tool_meta.get("result_fields", [])

        if not model_name or model_name not in env:
            return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' not found."}}

        try:
            # Security Rule: Execute tool strictly under authenticated caller's env.user context
            exec_user = env.user
            model_obj = env[model_name].with_user(exec_user)
            caps = ModelInspector.get_model_capabilities(model_obj)

            if not caps.get(operation, False):
                m_type = ModelInspector.detect_model_type(model_obj)
                return {
                    "success": False,
                    "error": {
                        "code": "unsupported_model_operation",
                        "message": f"Operation '{operation}' is not supported on {m_type.capitalize()} model '{model_name}'."
                    }
                }

            if operation == "search":
                if not env['mcp.model.rule'].check_permission(model_name, 'search'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Read permission is disabled for model '{model_name}'."}}
                domain = []
                if params and search_fields:
                    for sf in search_fields:
                        val = params.get(sf)
                        if val:
                            domain.append((sf, 'ilike', val))
                limit = min(max(int(params.get('limit', 20) if params else 20), 1), 100)
                offset = max(int(params.get('offset', 0) if params else 0), 0)

                read_f = ModelInspector.get_safe_fields(model_obj, requested_fields=result_fields if result_fields else None)
                records = model_obj.search_read(domain, fields=read_f, limit=limit, offset=offset)
                return {"success": True, "count": len(records), "records": records}

            elif operation == "read":
                if not env['mcp.model.rule'].check_permission(model_name, 'read'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Read permission is disabled for model '{model_name}'."}}
                rec_id = params.get('id') if params else None
                if not rec_id:
                    return {"success": False, "error": {"code": "missing_id", "message": "Record ID is required for read operation."}}
                rec = model_obj.browse(rec_id)
                if not rec.exists():
                    return {"success": False, "error": {"code": "record_not_found", "message": f"Record #{rec_id} not found."}}
                
                req_fields = result_fields if result_fields else (params.get('fields') if params else None)
                read_f = ModelInspector.get_safe_fields(model_obj, requested_fields=req_fields)
                
                try:
                    data = rec.read(read_f)[0]
                except Exception:
                    essential = ['id', 'name', 'display_name', 'email', 'phone', 'mobile', 'street', 'city', 'zip', 'country_id', 'company_name']
                    avail = [f for f in essential if f in model_obj._fields]
                    data = rec.read(avail)[0]

                cleaned = {}
                for k, v in data.items():
                    if isinstance(v, (bytes, bytearray)):
                        cleaned[k] = "<binary_data>"
                    else:
                        cleaned[k] = v
                return {"success": True, "id": rec_id, "data": cleaned}

            elif operation == "create":
                if not env['mcp.model.rule'].check_permission(model_name, 'create'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Create permission is disabled for model '{model_name}'."}}
                vals = params.get('values') or {}
                if not isinstance(vals, dict) or not vals:
                    return {"success": False, "error": {"code": "missing_values", "message": "Field values object is required for create operation."}}
                rec = model_obj.create(vals)
                return {"success": True, "id": rec.id, "display_name": rec.display_name}

            elif operation == "write":
                if not env['mcp.model.rule'].check_permission(model_name, 'write'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Update permission is disabled for model '{model_name}'."}}
                rec_id = params.get('id')
                vals = params.get('values') or {}
                if not rec_id:
                    return {"success": False, "error": {"code": "missing_id", "message": "Record ID is required for write operation."}}
                rec = model_obj.browse(rec_id)
                if not rec.exists():
                    return {"success": False, "error": {"code": "record_not_found", "message": f"Record #{rec_id} not found."}}
                rec.write(vals)
                return {"success": True, "id": rec_id, "updated_fields": list(vals.keys())}

            elif operation == "delete":
                if not env['mcp.model.rule'].check_permission(model_name, 'delete'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Delete permission is disabled for model '{model_name}'."}}
                rec_id = params.get('id')
                if not rec_id:
                    return {"success": False, "error": {"code": "missing_id", "message": "Record ID is required for delete operation."}}
                rec = model_obj.browse(rec_id)
                if not rec.exists():
                    return {"success": False, "error": {"code": "record_not_found", "message": f"Record #{rec_id} not found."}}
                rec.unlink()
                return {"success": True, "deleted_id": rec_id}

            elif operation == "aggregate":
                if not env['mcp.model.rule'].check_permission(model_name, 'read'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Read permission is disabled for model '{model_name}'."}}
                domain = params.get('domain', []) if params else []
                groupby = params.get('groupby', []) if params else []
                fields_agg = params.get('fields', []) if params else (result_fields or [])
                res = model_obj.read_group(domain=domain, fields=fields_agg, groupby=groupby)
                return {"success": True, "results": res}

            elif operation == "explain":
                if not env['mcp.model.rule'].check_permission(model_name, 'read'):
                    return {"success": False, "error": {"code": "access_denied", "message": f"Read permission is disabled for model '{model_name}'."}}
                field_info = model_obj.fields_get()
                rec_id = params.get('id') if params else None
                disp_name = model_obj.browse(rec_id).display_name if rec_id and model_obj.browse(rec_id).exists() else ""
                meta = {
                    "model": model_name,
                    "display_name": disp_name,
                    "field_count": len(field_info),
                    "fields": {}
                }
                for fname, fmeta in field_info.items():
                    if not result_fields or fname in result_fields:
                        meta["fields"][fname] = {
                            "label": fmeta.get("string", ""),
                            "type": fmeta.get("type", ""),
                            "relation": fmeta.get("relation", ""),
                            "required": fmeta.get("required", False),
                            "readonly": fmeta.get("readonly", False)
                        }
                return {"success": True, "meta": meta}

            else:
                return {"success": False, "error": {"code": "operation_not_allowed", "message": f"Operation '{operation}' not supported."}}

        except Exception as e:
            env.cr.rollback()
            import traceback
            tb_str = traceback.format_exc()
            _logger.error(f"Error in odoo_create_record for {model_name}: {e}\n{tb_str}")
            return {"success": False, "error": {"code": "orm_error", "message": str(e), "traceback": tb_str}}


# ==============================================================================
# READ-ONLY BUILT-IN TOOL IMPLEMENTATIONS

# ------------------------------------------------------------------------------
# CORE / TECHNICAL / GENERIC TOOLS
# ------------------------------------------------------------------------------

@mcp_tool(
    name="ping",
    description="Ping Odoo MCP Server to verify connection status",
    category="Technical",
    read_only=True,
    input_schema={"type": "object", "properties": {}}
)
@mcp_tool(
    name="odoo_ping",
    description="Ping Odoo MCP Server to verify connection status",
    category="Technical",
    read_only=True,
    input_schema={"type": "object", "properties": {}}
)
def handle_odoo_ping(env, params):
    return {"status": "online", "message": "Odoo MCP Server is active and operational."}

@mcp_tool(
    name="read_records",
    description="Generic Read Tool to fetch specific field values for a target record by ID.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"},
            "ids": {"type": "array", "items": {"type": "integer"}, "description": "Target record IDs"},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "List of fields to read"}
        },
        "required": ["model"]
    }
)
@mcp_tool(
    name="odoo_read_record",
    description="Generic Read Tool to fetch specific field values for a target record by ID.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "List of fields to read"}
        },
        "required": ["model", "id"]
    }
)
def handle_read_record(env, params):
    model_name = params.get('model')
    raw_id = params.get('id') or (params.get('ids')[0] if params.get('ids') and isinstance(params.get('ids'), list) and len(params.get('ids')) > 0 else None)
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    if raw_id is None:
        return {"success": False, "error": {"code": "missing_id", "message": "Record ID is required."}}
    try:
        rec_id = int(raw_id)
    except Exception:
        return {"success": False, "error": {"code": "invalid_id", "message": f"Record ID '{raw_id}' must be an integer."}}
    fields = params.get('fields')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    rec = env[model_name].browse(rec_id)
    if not rec.exists():
        return {"success": False, "error": {"code": "not_found", "message": f"Record #{rec_id} not found."}}
    
    if not fields:
        finfo = env[model_name].fields_get()
        fields = [
            fn for fn, fm in finfo.items()
            if fm.get('store', True) 
            and fm.get('type') not in ('binary', 'html')
            and not fn.startswith('message_') 
            and not fn.startswith('activity_')
        ]

    try:
        res = rec.read(fields)[0]
    except Exception:
        essential = ['id', 'name', 'display_name', 'email', 'phone', 'mobile', 'street', 'city', 'zip', 'country_id', 'company_name']
        avail = [f for f in essential if f in env[model_name]._fields]
        res = rec.read(avail)[0]

    cleaned = {k: ("<binary_data>" if isinstance(v, (bytes, bytearray)) else v) for k, v in res.items()}
    return {"success": True, "model": model_name, "id": rec_id, "data": cleaned}

@mcp_tool(
    name="search_read_records",
    description="Search and read records matching a domain filter.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "domain": {"type": "array", "description": "Search domain filters"},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to read"},
            "limit": {"type": "integer", "description": "Maximum records to return"},
            "offset": {"type": "integer", "description": "Record offset"}
        },
        "required": ["model"]
    }
)
@mcp_tool(
    name="odoo_search_read",
    description="Search and read records matching a domain filter.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "domain": {"type": "array", "description": "Search domain filters"},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to read"},
            "limit": {"type": "integer", "description": "Maximum records to return"},
            "offset": {"type": "integer", "description": "Record offset"}
        },
        "required": ["model"]
    }
)
def handle_search_read_records(env, params):
    model_name = params.get('model')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    
    domain = params.get('domain', [])
    if isinstance(domain, str):
        try:
            import ast
            domain = ast.literal_eval(domain)
        except Exception:
            domain = []
            
    limit = min(max(int(params.get('limit', 20) if params else 20), 1), 100)
    offset = max(int(params.get('offset', 0) if params else 0), 0)
    fields = params.get('fields')

    recs = env[model_name].search_read(domain, fields=fields, limit=limit, offset=offset)
    return {"success": True, "model": model_name, "count": len(recs), "records": recs}

@mcp_tool(
    name="odoo_aggregate",
    description="Compute aggregation (count, sum, average, min, max) on Odoo models.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "domain": {"type": "array", "description": "Search domain filters"},
            "groupby": {"type": "array", "items": {"type": "string"}},
            "fields": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["model", "fields"]
    }
)
def handle_aggregate(env, params):
    model_name = params.get('model')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    res = env[model_name].read_group(domain=params.get('domain', []), fields=params.get('fields', []), groupby=params.get('groupby', []))
    return {"success": True, "model": model_name, "results": res}

@mcp_tool(
    name="odoo_explain_record",
    description="Explain field structure, labels, types, and relations of any Odoo model.",
    category="Technical",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"}
        },
        "required": ["model"]
    }
)
def handle_explain_record(env, params):
    model_name = params.get('model')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    finfo = env[model_name].fields_get()
    return {"success": True, "model": model_name, "field_count": len(finfo), "fields": finfo}

@mcp_tool(
    name="create_record",
    description="Create a new record in any allowed Odoo model.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "values": {"type": "object", "description": "Field values to create record"}
        },
        "required": ["model", "values"]
    }
)
@mcp_tool(
    name="odoo_create_record",
    description="Create a new record in any allowed Odoo model.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "values": {"type": "object", "description": "Field values to create record"}
        },
        "required": ["model", "values"]
    }
)
def handle_create_record(env, params):
    model_name = params.get('model')
    values = params.get('values')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    rec = env[model_name].create(values)
    return {"success": True, "id": rec.id, "display_name": rec.display_name}

@mcp_tool(
    name="write_record",
    description="Update an existing record in any allowed Odoo model by ID.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"},
            "values": {"type": "object", "description": "Field values to update"}
        },
        "required": ["model", "id", "values"]
    }
)
@mcp_tool(
    name="odoo_write_record",
    description="Update an existing record in any allowed Odoo model by ID.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"},
            "values": {"type": "object", "description": "Field values to update"}
        },
        "required": ["model", "id", "values"]
    }
)
def handle_write_record(env, params):
    model_name = params.get('model')
    rec_id = params.get('id')
    values = params.get('values')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    rec = env[model_name].browse(rec_id)
    if not rec.exists():
        return {"success": False, "error": {"code": "not_found", "message": f"Record #{rec_id} not found."}}
    rec.write(values)
    return {"success": True, "id": rec_id, "display_name": rec.display_name}

@mcp_tool(
    name="delete_record",
    description="Delete an existing record in any allowed Odoo model by ID.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"}
        },
        "required": ["model", "id"]
    }
)
@mcp_tool(
    name="unlink_record",
    description="Delete an existing record in any allowed Odoo model by ID.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"}
        },
        "required": ["model", "id"]
    }
)
@mcp_tool(
    name="odoo_delete_record",
    description="Delete an existing record in any allowed Odoo model by ID.",
    category="Technical",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Target Odoo model name"},
            "id": {"type": "integer", "description": "Target record ID"}
        },
        "required": ["model", "id"]
    }
)
def handle_delete_record(env, params):
    model_name = params.get('model')
    rec_id = params.get('id')
    if not model_name or model_name not in env:
        return {"success": False, "error": {"code": "unknown_model", "message": f"Model '{model_name}' does not exist."}}
    rec = env[model_name].browse(rec_id)
    if not rec.exists():
        return {"success": False, "error": {"code": "not_found", "message": f"Record #{rec_id} not found."}}
    rec.unlink()
    return {"success": True, "deleted_id": rec_id}

# ------------------------------------------------------------------------------
# 1. CONTACTS APP (res.partner)
# ------------------------------------------------------------------------------

@mcp_tool(
    name="odoo_search_partners",
    description="Search Contacts & Customers by name, email, phone, or general search query.",
    category="Contacts",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Filter by contact name or search term"},
            "query": {"type": "string", "description": "General search query for name, email, or phone"},
            "email": {"type": "string", "description": "Filter by email address"},
            "phone": {"type": "string", "description": "Filter by phone number"},
            "limit": {"type": "integer", "default": 20, "description": "Max records to return"}
        }
    }
)
def handle_search_partners(env, params):
    if 'res.partner' not in env:
        return {"success": True, "count": 0, "records": [], "note": "Module not installed"}

    search_term = (params.get('name') or params.get('query') or params.get('search') or "").strip()
    domain = []
    if search_term:
        domain = ['|', '|', ('name', 'ilike', search_term), ('email', 'ilike', search_term), ('phone', 'ilike', search_term)]
    elif params.get('email'):
        domain = [('email', 'ilike', params['email'])]
    elif params.get('phone'):
        domain = [('phone', 'ilike', params['phone'])]

    records = env['res.partner'].search(domain, limit=params.get('limit', 20))
    return {
        "success": True,
        "count": len(records),
        "records": [
            {
                "id": r.id,
                "name": r.name,
                "email": r.email or "",
                "phone": r.phone or r.mobile or ""
            } for r in records
        ]
    }

@mcp_tool(name="odoo_get_contact", description="Get Contact details by ID", category="Contacts", read_only=True)
def handle_get_contact(env, params):
    if 'res.partner' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    p = env['res.partner'].browse(params.get('id'))
    if not p.exists(): return {"success": False, "error": {"code": "not_found", "message": "Contact not found"}}
    return {"success": True, "id": p.id, "name": p.name, "email": p.email or "", "phone": p.phone or p.mobile or ""}

@mcp_tool(name="odoo_create_contact", description="Create Contact or Company", category="Contacts", read_only=False)
def handle_create_contact(env, params):
    if 'res.partner' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    p = env['res.partner'].create({"name": params.get("name"), "email": params.get("email", ""), "phone": params.get("phone", "")})
    return {"success": True, "id": p.id, "name": p.name}

@mcp_tool(
    name="odoo_update_contact",
    description="Update Contact details (email, phone, mobile, name, street, etc.) by contact ID.",
    category="Contacts",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Target Odoo contact ID (res.partner)"},
            "email": {"type": "string", "description": "New email address"},
            "phone": {"type": "string", "description": "New phone number"},
            "mobile": {"type": "string", "description": "New mobile number"},
            "name": {"type": "string", "description": "New contact name"},
            "values": {"type": "object", "description": "Optional dictionary of field values to update"}
        },
        "required": ["id"]
    }
)
def handle_update_contact(env, params):
    if 'res.partner' not in env:
        return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}

    contact_id = params.get("id")
    if not contact_id:
        return {"success": False, "error": {"code": "missing_id", "message": "Contact ID is required."}}

    p = env['res.partner'].browse(contact_id)
    if not p.exists():
        return {"success": False, "error": {"code": "not_found", "message": f"Contact #{contact_id} not found."}}

    vals = {}
    if isinstance(params.get("values"), dict):
        vals.update(params["values"])

    for field in ['name', 'email', 'phone', 'mobile', 'street', 'city', 'zip', 'comment', 'function', 'title']:
        if field in params and params[field] is not None:
            vals[field] = params[field]

    if not vals:
        return {"success": False, "error": {"code": "missing_values", "message": "No valid fields to update provided."}}

    p.write(vals)
    return {
        "success": True,
        "id": p.id,
        "name": p.name,
        "email": p.email or "",
        "phone": p.phone or p.mobile or "",
        "updated_fields": list(vals.keys()),
        "message": f"Successfully updated contact '{p.name}' (ID #{p.id})."
    }

@mcp_tool(name="odoo_delete_contact", description="Delete Contact", category="Contacts", read_only=False)
def handle_delete_contact(env, params):
    if 'res.partner' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    p = env['res.partner'].browse(params.get("id"))
    if not p.exists(): return {"success": False, "error": {"code": "not_found", "message": "Contact not found"}}
    p.unlink()
    return {"success": True, "deleted_id": params.get("id")}

@mcp_tool(name="odoo_search_companies", description="Search Companies", category="Contacts", read_only=True)
def handle_search_companies(env, params):
    if 'res.partner' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    records = env['res.partner'].search([('is_company', '=', True)], limit=params.get('limit', 20))
    return {"success": True, "count": len(records), "records": [{"id": r.id, "name": r.name} for r in records]}

# ------------------------------------------------------------------------------
# 2. CRM APP (crm.lead)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_leads", description="Search CRM Leads", category="CRM", read_only=True)
def handle_search_leads(env, params):
    if 'crm.lead' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['crm.lead'].search([('type', '=', 'lead')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_opportunities", description="Search Opportunities", category="CRM", read_only=True)
def handle_search_opportunities(env, params):
    if 'crm.lead' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['crm.lead'].search([('type', '=', 'opportunity')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "stage": r.stage_id.name if r.stage_id else ""} for r in recs]}

@mcp_tool(name="odoo_create_lead", description="Create Lead/Opportunity", category="CRM", read_only=False)
def handle_create_lead(env, params):
    if 'crm.lead' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    user = env.user
    crm_obj = env['crm.lead'].with_user(user)
    
    vals = {
        "name": params.get("name", "New Opportunity"),
        "user_id": params.get("user_id") or user.id,
        "type": params.get("type", "opportunity")
    }
    if params.get("partner_id"):
        vals["partner_id"] = params.get("partner_id")
    if params.get("expected_revenue"):
        vals["expected_revenue"] = params.get("expected_revenue")
    if params.get("stage_id"):
        vals["stage_id"] = params.get("stage_id")

    l = crm_obj.create(vals)
    return {"success": True, "id": l.id, "name": l.name}

@mcp_tool(name="odoo_update_opportunity", description="Update Opportunity", category="CRM", read_only=False)
def handle_update_opportunity(env, params):
    if 'crm.lead' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    l = env['crm.lead'].browse(params.get("id"))
    if not l.exists(): return {"success": False, "error": {"code": "not_found", "message": "Opportunity not found"}}
    l.write(params.get("values", {}))
    return {"success": True, "id": l.id}

@mcp_tool(name="odoo_move_opportunity_stage", description="Move Opportunity Stage", category="CRM", read_only=False)
def handle_move_opportunity_stage(env, params):
    if 'crm.lead' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    l = env['crm.lead'].browse(params.get("id"))
    if not l.exists(): return {"success": False, "error": {"code": "not_found", "message": "Opportunity not found"}}
    if params.get("stage_id"): l.write({"stage_id": params.get("stage_id")})
    return {"success": True, "id": l.id, "stage": l.stage_id.name if l.stage_id else ""}

@mcp_tool(name="odoo_add_activity", description="Add Activity to Lead", category="CRM", read_only=False)
def handle_add_activity(env, params):
    if 'mail.activity' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    act = env['mail.activity'].create({
        "res_model_id": env['ir.model'].search([('model', '=', 'crm.lead')], limit=1).id,
        "res_id": params.get("lead_id", 1),
        "note": params.get("note", "Follow up")
    })
    return {"success": True, "id": act.id}

@mcp_tool(name="odoo_schedule_meeting", description="Schedule Meeting", category="CRM", read_only=False)
def handle_schedule_meeting(env, params):
    if 'calendar.event' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    ev = env['calendar.event'].create({"name": params.get("name", "Meeting"), "start": params.get("start")})
    return {"success": True, "id": ev.id, "name": ev.name}

# ------------------------------------------------------------------------------
# 3. SALES APP (sale.order)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_quotations", description="Search Sales Quotations", category="Sales", read_only=True)
def handle_search_quotations(env, params):
    if 'sale.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['sale.order'].search([('state', 'in', ['draft', 'sent'])], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "total": r.amount_total} for r in recs]}

@mcp_tool(name="odoo_search_orders", description="Search Sales Orders", category="Sales", read_only=True)
def handle_search_orders(env, params):
    if 'sale.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['sale.order'].search([('state', '=', 'sale')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "total": r.amount_total} for r in recs]}

@mcp_tool(name="odoo_create_quotation", description="Create Quotation", category="Sales", read_only=False)
def handle_create_quotation(env, params):
    if 'sale.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    so = env['sale.order'].create({"partner_id": params.get("partner_id", 1)})
    return {"success": True, "id": so.id, "name": so.name}

@mcp_tool(name="odoo_confirm_quotation", description="Confirm Sales Order", category="Sales", read_only=False)
def handle_confirm_quotation(env, params):
    if 'sale.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    so = env['sale.order'].browse(params.get("id"))
    if not so.exists(): return {"success": False, "error": {"code": "not_found", "message": "Order not found"}}
    so.action_confirm()
    return {"success": True, "id": so.id, "state": so.state}

@mcp_tool(name="odoo_update_sales_order", description="Update Sales Order", category="Sales", read_only=False)
def handle_update_sales_order(env, params):
    if 'sale.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    so = env['sale.order'].browse(params.get("id"))
    if not so.exists(): return {"success": False, "error": {"code": "not_found", "message": "Order not found"}}
    so.write(params.get("values", {}))
    return {"success": True, "id": so.id}

@mcp_tool(name="odoo_cancel_sales_order", description="Cancel Sales Order", category="Sales", read_only=False)
def handle_cancel_sales_order(env, params):
    if 'sale.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    so = env['sale.order'].browse(params.get("id"))
    if not so.exists(): return {"success": False, "error": {"code": "not_found", "message": "Order not found"}}
    so.action_cancel()
    return {"success": True, "id": so.id, "state": so.state}

# ------------------------------------------------------------------------------
# 4. PURCHASE APP (purchase.order)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_rfqs", description="Search Requests for Quotation", category="Purchase", read_only=True)
def handle_search_rfqs(env, params):
    if 'purchase.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['purchase.order'].search([('state', 'in', ['draft', 'sent'])], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_purchase_orders", description="Search Purchase Orders", category="Purchase", read_only=True)
def handle_search_purchase_orders(env, params):
    if 'purchase.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['purchase.order'].search([('state', '=', 'purchase')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_rfq", description="Create RFQ", category="Purchase", read_only=False)
def handle_create_rfq(env, params):
    if 'purchase.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    po = env['purchase.order'].create({"partner_id": params.get("partner_id", 1)})
    return {"success": True, "id": po.id, "name": po.name}

@mcp_tool(name="odoo_confirm_purchase_order", description="Confirm Purchase Order", category="Purchase", read_only=False)
def handle_confirm_purchase_order(env, params):
    if 'purchase.order' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    po = env['purchase.order'].browse(params.get("id"))
    if not po.exists(): return {"success": False, "error": {"code": "not_found", "message": "Order not found"}}
    po.button_confirm()
    return {"success": True, "id": po.id, "state": po.state}

@mcp_tool(name="odoo_search_vendors", description="Search Vendors", category="Purchase", read_only=True)
def handle_search_vendors(env, params):
    if 'res.partner' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['res.partner'].search([('supplier_rank', '>', 0)], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 5. INVENTORY APP (product.product, stock.quant, stock.picking)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_products", description="Search Products", category="Inventory", read_only=True)
def handle_search_products(env, params):
    if 'product.product' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['product.product'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "list_price": r.list_price} for r in recs]}

@mcp_tool(name="odoo_get_product", description="Get Product Info", category="Inventory", read_only=True)
def handle_get_product(env, params):
    if 'product.product' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    p = env['product.product'].browse(params.get("id"))
    if not p.exists(): return {"success": False, "error": {"code": "not_found", "message": "Product not found"}}
    return {"success": True, "id": p.id, "name": p.name, "list_price": p.list_price}

@mcp_tool(name="odoo_create_product", description="Create Product", category="Inventory", read_only=False)
def handle_create_product(env, params):
    if 'product.product' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    p = env['product.product'].create({"name": params.get("name"), "list_price": params.get("list_price", 0.0)})
    return {"success": True, "id": p.id, "name": p.name}

@mcp_tool(name="odoo_update_product", description="Update Product", category="Inventory", read_only=False)
def handle_update_product(env, params):
    if 'product.product' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    p = env['product.product'].browse(params.get("id"))
    if not p.exists(): return {"success": False, "error": {"code": "not_found", "message": "Product not found"}}
    p.write(params.get("values", {}))
    return {"success": True, "id": p.id}

@mcp_tool(name="odoo_search_stock", description="Search Stock Quants", category="Inventory", read_only=True)
def handle_search_stock(env, params):
    if 'stock.quant' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['stock.quant'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "product": r.product_id.name, "quantity": r.quantity} for r in recs]}

@mcp_tool(name="odoo_search_warehouses", description="Search Warehouses", category="Inventory", read_only=True)
def handle_search_warehouses(env, params):
    if 'stock.warehouse' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['stock.warehouse'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "code": r.code} for r in recs]}

@mcp_tool(name="odoo_search_locations", description="Search Stock Locations", category="Inventory", read_only=True)
def handle_search_locations(env, params):
    if 'stock.location' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['stock.location'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.complete_name} for r in recs]}

@mcp_tool(name="odoo_search_transfers", description="Search Stock Transfers", category="Inventory", read_only=True)
def handle_search_transfers(env, params):
    if 'stock.picking' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['stock.picking'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "state": r.state} for r in recs]}

@mcp_tool(name="odoo_validate_transfer", description="Validate Stock Transfer", category="Inventory", read_only=False)
def handle_validate_transfer(env, params):
    if 'stock.picking' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    p = env['stock.picking'].browse(params.get("id"))
    if not p.exists(): return {"success": False, "error": {"code": "not_found", "message": "Transfer not found"}}
    p.button_validate()
    return {"success": True, "id": p.id, "state": p.state}

# ------------------------------------------------------------------------------
# 6. ACCOUNTING APP (account.move, account.payment)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_invoices", description="Search Customer Invoices", category="Accounting", read_only=True)
def handle_search_invoices(env, params):
    if 'account.move' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.move'].search([('move_type', '=', 'out_invoice')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "total": r.amount_total} for r in recs]}

@mcp_tool(name="odoo_search_vendor_bills", description="Search Vendor Bills", category="Accounting", read_only=True)
def handle_search_vendor_bills(env, params):
    if 'account.move' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.move'].search([('move_type', '=', 'in_invoice')], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "total": r.amount_total} for r in recs]}

@mcp_tool(name="odoo_search_payments", description="Search Payments", category="Accounting", read_only=True)
def handle_search_payments(env, params):
    if 'account.payment' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.payment'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "amount": r.amount} for r in recs]}

@mcp_tool(name="odoo_create_invoice", description="Create Invoice", category="Accounting", read_only=False)
def handle_create_invoice(env, params):
    if 'account.move' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    inv = env['account.move'].create({"move_type": "out_invoice", "partner_id": params.get("partner_id", 1)})
    return {"success": True, "id": inv.id, "name": inv.name}

@mcp_tool(name="odoo_register_payment", description="Register Payment", category="Accounting", read_only=False)
def handle_register_payment(env, params):
    if 'account.payment' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    pay = env['account.payment'].create({"amount": params.get("amount", 10.0), "partner_id": params.get("partner_id", 1)})
    return {"success": True, "id": pay.id, "name": pay.name}

@mcp_tool(name="odoo_search_journals", description="Search Accounting Journals", category="Accounting", read_only=True)
def handle_search_journals(env, params):
    if 'account.journal' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.journal'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "code": r.code} for r in recs]}

@mcp_tool(name="odoo_search_taxes", description="Search Taxes", category="Accounting", read_only=True)
def handle_search_taxes(env, params):
    if 'account.tax' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.tax'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "amount": r.amount} for r in recs]}

# ------------------------------------------------------------------------------
# 7. PROJECTS APP (project.project, project.task)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_projects", description="Search Projects", category="Projects", read_only=True)
def handle_search_projects(env, params):
    if 'project.project' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['project.project'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_tasks", description="Search Tasks", category="Projects", read_only=True)
def handle_search_tasks(env, params):
    if 'project.task' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['project.task'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_task", description="Create Task", category="Projects", read_only=False)
def handle_create_task(env, params):
    if 'project.task' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    t = env['project.task'].create({"name": params.get("name")})
    return {"success": True, "id": t.id, "name": t.name}

@mcp_tool(name="odoo_update_task", description="Update Task", category="Projects", read_only=False)
def handle_update_task(env, params):
    if 'project.task' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    t = env['project.task'].browse(params.get("id"))
    if not t.exists(): return {"success": False, "error": {"code": "not_found", "message": "Task not found"}}
    t.write(params.get("values", {}))
    return {"success": True, "id": t.id}

@mcp_tool(name="odoo_complete_task", description="Mark Task Completed", category="Projects", read_only=False)
def handle_complete_task(env, params):
    if 'project.task' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    t = env['project.task'].browse(params.get("id"))
    if not t.exists(): return {"success": False, "error": {"code": "not_found", "message": "Task not found"}}
    t.write({"stage_id": params.get("done_stage_id", 1)})
    return {"success": True, "id": t.id}

# ------------------------------------------------------------------------------
# 8. HELPDESK APP (helpdesk.ticket)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_tickets", description="Search Tickets", category="Helpdesk", read_only=True)
def handle_search_tickets(env, params):
    if 'helpdesk.ticket' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['helpdesk.ticket'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_ticket", description="Create Ticket", category="Helpdesk", read_only=False)
def handle_create_ticket(env, params):
    if 'helpdesk.ticket' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    t = env['helpdesk.ticket'].create({"name": params.get("name")})
    return {"success": True, "id": t.id, "name": t.name}

@mcp_tool(name="odoo_update_ticket", description="Update Ticket", category="Helpdesk", read_only=False)
def handle_update_ticket(env, params):
    if 'helpdesk.ticket' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    t = env['helpdesk.ticket'].browse(params.get("id"))
    if not t.exists(): return {"success": False, "error": {"code": "not_found", "message": "Ticket not found"}}
    t.write(params.get("values", {}))
    return {"success": True, "id": t.id}

# ------------------------------------------------------------------------------
# 9. EMPLOYEES & HR (hr.employee, hr.department, hr.leave, hr.attendance)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_employees", description="Search Employees", category="Employees", read_only=True)
def handle_search_employees(env, params):
    if 'hr.employee' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['hr.employee'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_departments", description="Search Departments", category="Employees", read_only=True)
def handle_search_departments(env, params):
    if 'hr.department' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['hr.department'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_leaves", description="Search Leaves", category="Employees", read_only=True)
def handle_search_leaves(env, params):
    if 'hr.leave' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['hr.leave'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_attendance", description="Search Attendance", category="Employees", read_only=True)
def handle_search_attendance(env, params):
    if 'hr.attendance' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['hr.attendance'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "employee": r.employee_id.name} for r in recs]}

# ------------------------------------------------------------------------------
# 10. CALENDAR APP (calendar.event)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_events", description="Search Calendar Events", category="Calendar", read_only=True)
def handle_search_events(env, params):
    if 'calendar.event' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['calendar.event'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_event", description="Create Event", category="Calendar", read_only=False)
def handle_create_event(env, params):
    if 'calendar.event' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    ev = env['calendar.event'].create({"name": params.get("name")})
    return {"success": True, "id": ev.id, "name": ev.name}

@mcp_tool(name="odoo_update_event", description="Update Event", category="Calendar", read_only=False)
def handle_update_event(env, params):
    if 'calendar.event' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    ev = env['calendar.event'].browse(params.get("id"))
    if not ev.exists(): return {"success": False, "error": {"code": "not_found", "message": "Event not found"}}
    ev.write(params.get("values", {}))
    return {"success": True, "id": ev.id}

# ------------------------------------------------------------------------------
# 11. DISCUSS APP (mail.channel, mail.message)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_channels", description="Search Channels", category="Discuss", read_only=True)
def handle_search_channels(env, params):
    if 'mail.channel' not in env and 'discuss.channel' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    mname = 'discuss.channel' if 'discuss.channel' in env else 'mail.channel'
    recs = env[mname].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_messages", description="Search Messages", category="Discuss", read_only=True)
def handle_search_messages(env, params):
    if 'mail.message' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['mail.message'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "body": r.body} for r in recs]}

# ------------------------------------------------------------------------------
# 12. MANUFACTURING APP (mrp.production, mrp.bom)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_manufacturing_orders", description="Search MOs", category="Manufacturing", read_only=True)
def handle_search_manufacturing_orders(env, params):
    if 'mrp.production' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['mrp.production'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_manufacturing_order", description="Create MO", category="Manufacturing", read_only=False)
def handle_create_manufacturing_order(env, params):
    if 'mrp.production' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    mo = env['mrp.production'].create({"product_id": params.get("product_id", 1)})
    return {"success": True, "id": mo.id, "name": mo.name}

@mcp_tool(name="odoo_search_boms", description="Search Bills of Materials", category="Manufacturing", read_only=True)
def handle_search_boms(env, params):
    if 'mrp.bom' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['mrp.bom'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "code": r.code} for r in recs]}

# ------------------------------------------------------------------------------
# 13. QUALITY APP (quality.check, quality.alert)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_quality_checks", description="Search Quality Checks", category="Quality", read_only=True)
def handle_search_quality_checks(env, params):
    if 'quality.check' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['quality.check'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_quality_alerts", description="Search Quality Alerts", category="Quality", read_only=True)
def handle_search_quality_alerts(env, params):
    if 'quality.alert' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['quality.alert'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 14. MAINTENANCE APP (maintenance.equipment, maintenance.request)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_equipment", description="Search Equipment", category="Maintenance", read_only=True)
def handle_search_equipment(env, params):
    if 'maintenance.equipment' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['maintenance.equipment'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_maintenance_requests", description="Search Maintenance Requests", category="Maintenance", read_only=True)
def handle_search_maintenance_requests(env, params):
    if 'maintenance.request' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['maintenance.request'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 15. DOCUMENTS APP (documents.document, documents.folder)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_documents", description="Search Documents", category="Documents", read_only=True)
def handle_search_documents(env, params):
    if 'documents.document' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['documents.document'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_folders", description="Search Folders", category="Documents", read_only=True)
def handle_search_folders(env, params):
    if 'documents.folder' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['documents.folder'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 16. KNOWLEDGE APP (knowledge.article)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_articles", description="Search Knowledge Articles", category="Knowledge", read_only=True)
def handle_search_articles(env, params):
    if 'knowledge.article' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['knowledge.article'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 17. WEBSITE APP (website.page, blog.post)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_pages", description="Search Website Pages", category="Website", read_only=True)
def handle_search_pages(env, params):
    if 'website.page' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['website.page'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "url": r.url} for r in recs]}

@mcp_tool(name="odoo_search_blog_posts", description="Search Blog Posts", category="Website", read_only=True)
def handle_search_blog_posts(env, params):
    if 'blog.post' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['blog.post'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 18. MARKETING APP (utm.campaign, mailing.list, mailing.contact)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_campaigns", description="Search Campaigns", category="Marketing", read_only=True)
def handle_search_campaigns(env, params):
    if 'utm.campaign' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['utm.campaign'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_mailing_lists", description="Search Mailing Lists", category="Marketing", read_only=True)
def handle_search_mailing_lists(env, params):
    if 'mailing.list' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['mailing.list'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_marketing_contacts", description="Search Marketing Contacts", category="Marketing", read_only=True)
def handle_search_marketing_contacts(env, params):
    if 'mailing.contact' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['mailing.contact'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "email": r.email} for r in recs]}

# ------------------------------------------------------------------------------
# 19. POS APP (pos.order, pos.session)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_pos_orders", description="Search POS Orders", category="POS", read_only=True)
def handle_search_pos_orders(env, params):
    if 'pos.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['pos.order'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "total": r.amount_total} for r in recs]}

@mcp_tool(name="odoo_search_pos_sessions", description="Search POS Sessions", category="POS", read_only=True)
def handle_search_pos_sessions(env, params):
    if 'pos.session' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['pos.session'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "state": r.state} for r in recs]}

# ------------------------------------------------------------------------------
# 20. RENTAL & SUBSCRIPTION (sale.order)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_rental_orders", description="Search Rental Orders", category="Rental", read_only=True)
def handle_search_rental_orders(env, params):
    if 'sale.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['sale.order'].search([('is_rental_order', '=', True)], limit=params.get('limit', 20)) if 'is_rental_order' in env['sale.order']._fields else []
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_search_subscriptions", description="Search Subscriptions", category="Subscription", read_only=True)
def handle_search_subscriptions(env, params):
    if 'sale.order' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['sale.order'].search([('is_subscription', '=', True)], limit=params.get('limit', 20)) if 'is_subscription' in env['sale.order']._fields else []
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

# ------------------------------------------------------------------------------
# 21. EXPENSES & TIMESHEETS (hr.expense, account.analytic.line)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_expenses", description="Search Expenses", category="Expenses", read_only=True)
def handle_search_expenses(env, params):
    if 'hr.expense' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['hr.expense'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name} for r in recs]}

@mcp_tool(name="odoo_create_expense", description="Create Expense Claim", category="Expenses", read_only=False)
def handle_create_expense(env, params):
    if 'hr.expense' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    ex = env['hr.expense'].create({"name": params.get("name"), "product_id": params.get("product_id", 1)})
    return {"success": True, "id": ex.id, "name": ex.name}

@mcp_tool(name="odoo_search_timesheets", description="Search Timesheets", category="Timesheets", read_only=True)
def handle_search_timesheets(env, params):
    if 'account.analytic.line' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['account.analytic.line'].search([('project_id', '!=', False)], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.name, "hours": r.unit_amount} for r in recs]}

@mcp_tool(name="odoo_create_timesheet_entry", description="Create Timesheet Entry", category="Timesheets", read_only=False)
def handle_create_timesheet_entry(env, params):
    if 'account.analytic.line' not in env: return {"success": False, "error": {"code": "module_not_installed", "message": "Module not installed"}}
    ts = env['account.analytic.line'].create({"name": params.get("name"), "project_id": params.get("project_id", 1), "unit_amount": params.get("hours", 1.0)})
    return {"success": True, "id": ts.id, "name": ts.name}

# ------------------------------------------------------------------------------
# 22. SIGN APP (sign.request)
# ------------------------------------------------------------------------------

@mcp_tool(name="odoo_search_signature_requests", description="Search Signature Requests", category="Sign", read_only=True)
def handle_search_signature_requests(env, params):
    if 'sign.request' not in env: return {"success": True, "count": 0, "records": [], "note": "Module not installed"}
    recs = env['sign.request'].search([], limit=params.get('limit', 20))
    return {"success": True, "count": len(recs), "records": [{"id": r.id, "name": r.reference} for r in recs]}


# ------------------------------------------------------------------------------
# 23. AI-POWERED ANALYTICS DASHBOARD GENERATION & MANAGEMENT
# ------------------------------------------------------------------------------

@mcp_tool(
    name="odoo_generate_analytics_dashboard",
    description="Generate an interactive BI Analytics Dashboard with live Odoo ORM data, KPI cards, charts (line, bar, pie, donut, area), leaderboards, and data tables. Automatically saves the dashboard in Odoo and opens it immediately on screen.",
    category="Analytics & BI",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title of the analytics dashboard (e.g. Sales Performance Dashboard)"},
            "description": {"type": "string", "description": "Summary of insights and metrics"},
            "category": {"type": "string", "default": "sales", "description": "Category: sales, crm, purchase, inventory, accounting, hr, project, helpdesk, manufacturing, custom"},
            "widgets": {
                "type": "array",
                "description": "List of chart and KPI widget configurations",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Widget or Chart Title"},
                        "widget_type": {"type": "string", "description": "Widget type: kpi_card, line_chart, bar_chart, pie_chart, donut_chart, area_chart, table, pivot, progress"},
                        "model_name": {"type": "string", "description": "Target Odoo model (e.g. sale.order, crm.lead, account.move, res.partner, stock.quant, hr.employee)"},
                        "domain": {"type": "array", "description": "Odoo search domain filters"},
                        "groupby_field": {"type": "string", "description": "Field to group by (e.g. date_order:month, user_id, stage_id, country_id)"},
                        "measure_field": {"type": "string", "description": "Field to aggregate (e.g. amount_total, expected_revenue, id)"},
                        "aggregation_type": {"type": "string", "default": "sum", "description": "sum, avg, count, min, max"},
                        "kpi_value_format": {"type": "string", "default": "currency", "description": "currency, number, percentage"},
                        "color_theme": {"type": "string", "default": "#4f46e5"},
                        "icon": {"type": "string", "default": "fa-line-chart"},
                        "trend_badge": {"type": "string", "description": "e.g. +14.2% vs last month"}
                    },
                    "required": ["name", "widget_type", "model_name"]
                }
            }
        },
        "required": ["title", "widgets"]
    }
)
def handle_generate_analytics_dashboard(env, params):
    title = params.get('title', 'AI Analytics Dashboard')
    desc = params.get('description', '')
    raw_cat = params.get('category', 'custom')
    valid_cats = ['sales', 'crm', 'finance', 'inventory', 'hr', 'project', 'custom']
    category = raw_cat if raw_cat in valid_cats else ('sales' if 'sale' in str(raw_cat).lower() else 'custom')
    widgets = params.get('widgets', [])

    dashboard_model = env['mcp.analytics.dashboard'].sudo()
    widget_model = env['mcp.dashboard.widget'].sudo()

    dashboard = dashboard_model.create({
        'name': title,
        'description': desc,
        'category': category,
        'is_favorite': True
    })

    widget_objs = []
    for seq, w in enumerate(widgets, start=1):
        target_model = w.get('model_name', 'crm.lead')
        if target_model not in env and 'crm.lead' in env:
            target_model = 'crm.lead'
            
        m_field = w.get('measure_field', 'id')
        if target_model == 'crm.lead' and m_field == 'amount_total':
            m_field = 'expected_revenue'

        domain_str = json.dumps(w.get('domain', []))
        w_rec = widget_model.create({
            'dashboard_id': dashboard.id,
            'name': w.get('name', f"Widget #{seq}"),
            'widget_type': w.get('widget_type', 'kpi_card'),
            'model_name': target_model,
            'domain_json': domain_str,
            'groupby_field': w.get('groupby_field', ''),
            'measure_field': m_field,
            'aggregation_type': w.get('aggregation_type', 'count'),
            'sequence': seq * 10,
            'color_theme': w.get('color_theme', '#4f46e5'),
            'icon': w.get('icon', 'fa-line-chart'),
            'kpi_value_format': w.get('kpi_value_format', 'number'),
            'trend_badge': w.get('trend_badge', '')
        })
        widget_objs.append(w_rec)

    return {
        "success": True,
        "dashboard_id": dashboard.id,
        "title": dashboard.name,
        "category": dashboard.category,
        "widget_count": len(widget_objs),
        "message": f"Successfully generated analytics dashboard '{dashboard.name}' with {len(widget_objs)} widgets.",
        "open_action": {
            "type": "ir.actions.client",
            "tag": "mcp_claude.control_center",
            "params": {
                "tab": "dashboards",
                "dashboard_id": dashboard.id
            }
        }
    }

@mcp_tool(
    name="odoo_update_analytics_dashboard",
    description="Update or refine an open BI Analytics Dashboard in Odoo (add new charts, replace KPIs, modify groupings, update filters).",
    category="Analytics & BI",
    read_only=False,
    input_schema={
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "integer", "description": "Target Dashboard ID (optional, defaults to most recent)"},
            "title": {"type": "string", "description": "New dashboard title if renaming"},
            "add_widgets": {
                "type": "array",
                "description": "New widgets/charts to add to the dashboard",
                "items": {"type": "object"}
            },
            "remove_widget_ids": {"type": "array", "items": {"type": "integer"}}
        }
    }
)
def handle_update_analytics_dashboard(env, params):
    dashboard_model = env['mcp.analytics.dashboard'].sudo()
    widget_model = env['mcp.dashboard.widget'].sudo()

    dash_id = params.get('dashboard_id')
    if dash_id:
        dash = dashboard_model.browse(dash_id)
    else:
        dash = dashboard_model.search([], limit=1, order='id desc')

    if not dash or not dash.exists():
        return {"success": False, "error": {"code": "not_found", "message": "Dashboard not found."}}

    if params.get('title'):
        dash.write({'name': params.get('title')})

    if params.get('remove_widget_ids'):
        rem_widgets = widget_model.browse(params.get('remove_widget_ids'))
        rem_widgets.unlink()

    if params.get('add_widgets'):
        curr_seq = max(dash.widget_ids.mapped('sequence') or [0]) + 10
        for w in params.get('add_widgets'):
            domain_str = json.dumps(w.get('domain', []))
            widget_model.create({
                'dashboard_id': dash.id,
                'name': w.get('name', 'New Chart'),
                'widget_type': w.get('widget_type', 'kpi_card'),
                'model_name': w.get('model_name', 'sale.order'),
                'domain_json': domain_str,
                'groupby_field': w.get('groupby_field', ''),
                'measure_field': w.get('measure_field', 'id'),
                'aggregation_type': w.get('aggregation_type', 'count'),
                'sequence': curr_seq,
                'color_theme': w.get('color_theme', '#10b981'),
                'icon': w.get('icon', 'fa-line-chart'),
                'kpi_value_format': w.get('kpi_value_format', 'number'),
                'trend_badge': w.get('trend_badge', '')
            })
            curr_seq += 10

    return {
        "success": True,
        "dashboard_id": dash.id,
        "title": dash.name,
        "widget_count": len(dash.widget_ids),
        "message": f"Successfully updated dashboard '{dash.name}'."
    }

@mcp_tool(
    name="odoo_list_analytics_dashboards",
    description="List all saved AI BI Analytics Dashboards in Odoo.",
    category="Analytics & BI",
    read_only=True,
    input_schema={
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "is_favorite": {"type": "boolean"}
        }
    }
)
def handle_list_analytics_dashboards(env, params):
    domain = []
    if params.get('category'):
        domain.append(('category', '=', params.get('category')))
    if params.get('is_favorite') is not None:
        domain.append(('is_favorite', '=', params.get('is_favorite')))

    recs = env['mcp.analytics.dashboard'].sudo().search(domain, order='is_favorite desc, sequence asc, id desc')
    result = []
    for r in recs:
        result.append({
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'category': r.category,
            'is_favorite': r.is_favorite,
            'widget_count': r.widget_count,
            'created_by': r.user_id.name,
            'create_date': str(r.create_date) if r.create_date else ''
        })
    return {"success": True, "count": len(result), "dashboards": result}


# ------------------------------------------------------------------------------
# THIRD-PARTY INTEGRATIONS (Twilio Power Dialer)
# ------------------------------------------------------------------------------

@mcp_tool(
    name="twilio_dial_contact",
    description="Initiate a voice call to an Odoo contact (res.partner) by partner_id or phone number via Twilio Power Dialer. When calling the active contact or a contact ID, pass partner_id (e.g. partner_id: 134). The system automatically resolves the contact's name and phone number from Odoo ORM.",
    category="Third Party",
    read_only=False,
    requires_approval=True,
    input_schema={
        "type": "object",
        "properties": {
            "partner_id": {"type": "integer", "description": "Target Odoo contact ID (res.partner)"},
            "phone": {"type": "string", "description": "Optional phone number to call in E.164 format"}
        }
    }
)
def handle_twilio_dial_contact(env, params):
    phone = (params.get("phone") or "").strip()
    partner_id = params.get("partner_id")

    target_name = "Contact"
    if partner_id:
        try:
            # NO sudo(): Strictly respect current user's Odoo ACLs and record rules
            partner = env['res.partner'].browse(partner_id)
            if partner.exists():
                target_name = partner.name or "Contact"
                if not phone:
                    phone = partner.phone or partner.mobile or ""
            else:
                return {
                    "success": False,
                    "error": {
                        "code": "record_not_found",
                        "message": f"Contact #{partner_id} not found."
                    }
                }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "access_denied",
                    "message": f"Access Denied: Unable to access contact #{partner_id} under current user permissions ({str(e)})."
                }
            }

    if not phone:
        return {
            "success": False,
            "error": {
                "code": "missing_phone",
                "message": "A valid phone number or partner_id with a phone number is required to place a call."
            }
        }

    # Fetch configured caller number securely from mcp.server.config or twilio.service
    config = env['mcp.server.config'].sudo().search([], limit=1)
    from_number = config.get_twilio_caller_number() if config else ""
    if not from_number and 'twilio.service' in env:
        from_number = env['twilio.service'].get_twilio_phone_number()

    # Create explicit pending approval request record in Odoo ORM
    approval_rec = None
    if 'mcp.approval.request' in env:
        try:
            import json
            approval_rec = env['mcp.approval.request'].sudo().create({
                'name': f"Twilio Call to {target_name} ({phone})",
                'tool_name': 'twilio_dial_contact',
                'arguments': json.dumps({'phone': phone, 'partner_id': partner_id, 'from_number': from_number}),
                'state': 'pending'
            })
        except Exception as e:
            _logger.warning(f"Failed to create mcp.approval.request: {e}")

    approval_id = approval_rec.id if approval_rec else None

    # PHASE 2 / 3 SAFETY REQUIREMENT: External Call Confirmation Protection
    # Tool invocation registers the request but DEFERS actual Twilio API call until explicit user confirmation.
    return {
        "success": True,
        "requires_user_confirmation": True,
        "status": "pending_approval",
        "approval_id": approval_id,
        "message": f"Twilio dial request for {target_name} ({phone}) registered and pending user approval (Approval ID #{approval_id}). Actual call execution is deferred.",
        "call_details": {
            "approval_id": approval_id,
            "partner_id": partner_id,
            "phone": phone,
            "from_number": from_number,
            "execution_status": "deferred_until_user_approval"
        }
    }


@mcp_tool(
    name="twilio_create_dialer_queue",
    description="Create an Auto Dialer Queue in Twilio Power Dialer for specified Odoo contact IDs (res.partner).",
    category="Third Party",
    read_only=False,
    requires_approval=False,
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Optional name for the Auto Dialer Campaign Queue"},
            "partner_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of Odoo contact IDs (res.partner) to add to the queue"
            },
            "contacts": {
                "type": "array",
                "description": "Alternative array of contact objects containing partner_id",
                "items": {
                    "type": "object",
                    "properties": {
                        "partner_id": {"type": "integer"}
                    }
                }
            },
            "require_approval": {"type": "boolean", "default": False, "description": "Set True to create a pending approval request instead of persisting queue immediately"}
        }
    }
)
def handle_twilio_create_dialer_queue(env, params):
    raw_name = (params.get("name") or "").strip()
    raw_ids = params.get("partner_ids") or []
    if not raw_ids and params.get("contacts"):
        raw_ids = [c.get("partner_id") for c in params.get("contacts") if isinstance(c, dict) and c.get("partner_id")]

    # Sanitize partner_ids to clean integers
    requested_ids = []
    for pid in raw_ids:
        try:
            val = int(pid)
            if val > 0:
                requested_ids.append(val)
        except (ValueError, TypeError):
            continue

    requested_count = len(requested_ids)

    if not requested_count:
        return {
            "success": False,
            "error": {
                "code": "missing_partner_ids",
                "message": "At least one valid res.partner ID is required to create an Auto Dialer Queue."
            }
        }

    # 1. Non-sudo Permission Check: Respect current user ACLs and Record Rules strictly
    accessible_partners = env['res.partner']
    inaccessible_ids = []
    for pid in requested_ids:
        try:
            partner = env['res.partner'].browse(pid)
            if partner.exists():
                # Force read access check under current user
                _ = partner.name
                accessible_partners |= partner
            else:
                inaccessible_ids.append(pid)
        except Exception:
            inaccessible_ids.append(pid)

    accessible_count = len(accessible_partners)

    if not accessible_count:
        return {
            "success": False,
            "error": {
                "code": "access_denied",
                "message": f"Access Denied or Records Not Found: None of the requested partner IDs {requested_ids} could be accessed under current user permissions."
            }
        }

    # 2. Phase 3 Approval Mechanism Check
    if params.get("require_approval", False):
        approval_rec = None
        if 'mcp.approval.request' in env:
            try:
                import json
                approval_rec = env['mcp.approval.request'].sudo().create({
                    'name': f"Twilio Dialer Queue ({accessible_count} Contacts)",
                    'tool_name': 'twilio_create_dialer_queue',
                    'arguments': json.dumps({'name': raw_name, 'partner_ids': accessible_partners.ids}),
                    'state': 'pending'
                })
            except Exception as e:
                _logger.warning(f"Failed to create mcp.approval.request for queue: {e}")

        app_id = approval_rec.id if approval_rec else None
        return {
            "success": True,
            "requires_user_confirmation": True,
            "status": "pending_approval",
            "approval_id": app_id,
            "requested_contacts": requested_count,
            "accessible_contacts": accessible_count,
            "skipped_inaccessible": len(inaccessible_ids),
            "message": f"Auto Dialer Queue creation for {accessible_count} contacts registered and pending user approval (Approval ID #{app_id}). Queue persistence is deferred until approval.",
        }

    # 3. Create Queue in Odoo Model 'twilio.auto.dialer'
    if 'twilio.auto.dialer' not in env:
        return {
            "success": False,
            "error": {
                "code": "module_not_installed",
                "message": "Twilio Power Dialer module (twilio_dialer) is not installed in Odoo."
            }
        }

    queue_name = raw_name or f"Auto Dialer Queue ({accessible_count} Contacts)"

    try:
        dialer_model = env['twilio.auto.dialer']
        queue = dialer_model.create({
            'name': queue_name,
            'partner_ids': [(6, 0, accessible_partners.ids)]
        })

        # 4. Post-verify actual queue line records created by ORM
        lines = env['twilio.auto.dialer.line'].search([('dialer_id', '=', queue.id)])
        queued_members_count = len(lines)
        queued_partner_ids = lines.mapped('partner_id.id')
        no_phone_partners = accessible_partners.filtered(lambda p: p.id not in queued_partner_ids)
        skipped_no_phone_count = len(no_phone_partners)
        skipped_inaccessible_count = len(inaccessible_ids)

        return {
            "success": True,
            "queue_id": queue.id,
            "queue_name": queue.name,
            "requested_contacts": requested_count,
            "accessible_contacts": accessible_count,
            "queued_members": queued_members_count,
            "skipped_inaccessible": skipped_inaccessible_count,
            "skipped_no_phone": skipped_no_phone_count,
            "partner_ids": queued_partner_ids,
            "message": f"Successfully created Auto Dialer Queue '{queue.name}' (ID #{queue.id}) with {queued_members_count} verified queued members ({skipped_no_phone_count} skipped due to missing phone numbers, {skipped_inaccessible_count} skipped due to access restrictions)."
        }
    except Exception as e:
        _logger.error(f"Error creating twilio.auto.dialer queue: {e}")
        return {
            "success": False,
            "error": {
                "code": "orm_creation_error",
                "message": f"Failed to create Auto Dialer Queue: {str(e)}"
            }
        }


