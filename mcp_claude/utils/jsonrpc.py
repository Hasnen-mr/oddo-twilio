# -*- coding: utf-8 -*-
"""
Stateless JSON-RPC 2.0 & Wire Format Utilities for mcp_claude
Zero ORM dependencies for maximum performance and unit testability.
"""

import json
from typing import Optional, Dict, Any, Union

def format_jsonrpc_success(request_id: Optional[Union[str, int]], result: Any) -> Dict[str, Any]:
    """Format standard JSON-RPC 2.0 success response payload."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }

def format_jsonrpc_error(request_id: Optional[Union[str, int]], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    """Format standard JSON-RPC 2.0 error response payload."""
    err_dict = {
        "code": code,
        "message": message
    }
    if data is not None:
        err_dict["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": err_dict
    }

def parse_jsonrpc_request(raw_data: Union[str, bytes, dict]) -> Dict[str, Any]:
    """Parse raw incoming string or dict into validated JSON-RPC structure."""
    if isinstance(raw_data, (str, bytes)):
        try:
            data = json.loads(raw_data)
        except Exception as e:
            return {"valid": False, "error": f"Invalid JSON payload: {e}", "id": None}
    elif isinstance(raw_data, dict):
        data = raw_data
    else:
        return {"valid": False, "error": "Payload must be JSON string or dict", "id": None}

    if not isinstance(data, dict):
        return {"valid": False, "error": "JSON-RPC request must be an object", "id": None}

    req_id = data.get("id")
    jsonrpc_ver = data.get("jsonrpc")
    method = data.get("method")
    params = data.get("params", {})

    if jsonrpc_ver != "2.0":
        return {"valid": False, "error": "Invalid or missing 'jsonrpc' version. Must be '2.0'", "id": req_id}

    if not method or not isinstance(method, str):
        return {"valid": False, "error": "Missing or invalid 'method' field", "id": req_id}

    return {
        "valid": True,
        "id": req_id,
        "method": method,
        "params": params if isinstance(params, (dict, list)) else {},
        "is_notification": req_id is None
    }
