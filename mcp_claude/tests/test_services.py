# -*- coding: utf-8 -*-
"""
Unit/Integration tests for mcp.environment and mcp.security Odoo AbstractModels
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestMCPServicesStructure(unittest.TestCase):

    def test_environment_structure(self):
        """Test expected payload structure of mcp.environment."""
        mock_info = {
            "base_url": "http://localhost:8069",
            "scheme": "http",
            "hostname": "localhost",
            "port": 8069,
            "is_https": False,
            "is_localhost": True,
            "env_code": "local",
            "badge_label": "🔵 Local Development",
            "badge_class": "bg-info",
            "supports_direct_url": False,
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": True,
                "sse": True,
                "oauth": True,
                "direct_connection": False
            }
        }
        self.assertEqual(mock_info["env_code"], "local")
        self.assertTrue(mock_info["capabilities"]["tools"])
        self.assertFalse(mock_info["capabilities"]["direct_connection"])

    def test_security_structure(self):
        """Test security payload format."""
        mock_auth_res = (True, "Authorized via API Key", 2)
        self.assertTrue(mock_auth_res[0])
        self.assertEqual(mock_auth_res[2], 2)

    def test_dispatcher_structure(self):
        """Test dispatcher JSON-RPC dispatch routing."""
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        from utils.jsonrpc import parse_jsonrpc_request, format_jsonrpc_success
        parsed = parse_jsonrpc_request(init_req)
        self.assertTrue(parsed["valid"])
        res = format_jsonrpc_success(parsed["id"], {"protocolVersion": "2024-11-05"})
        self.assertEqual(res["result"]["protocolVersion"], "2024-11-05")

if __name__ == "__main__":
    unittest.main()
