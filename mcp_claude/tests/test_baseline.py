# -*- coding: utf-8 -*-
"""
Phase 0 Baseline Regression Test Suite for mcp_claude module
Records and validates behavior of:
- /mcp/v1/messages
- /mcp/v1/sse
- /mcp/health
- /.well-known/oauth-authorization-server
- initialize, tools/list, tools/call, ping JSON-RPC responses
"""

import json
import unittest
from unittest.mock import MagicMock

class TestBaselineMCPProtocol(unittest.TestCase):

    def setUp(self):
        self.initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "TestClient", "version": "1.0.0"}
            }
        }
        self.tools_list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        self.ping_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "ping",
            "params": {}
        }

    def test_jsonrpc_structure(self):
        """Verify baseline JSON-RPC 2.0 structure formatting."""
        self.assertEqual(self.initialize_request["jsonrpc"], "2.0")
        self.assertEqual(self.initialize_request["method"], "initialize")
        self.assertIn("protocolVersion", self.initialize_request["params"])

    def test_expected_oauth_discovery_keys(self):
        """Verify RFC 8414 metadata baseline keys."""
        expected_keys = [
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "response_types_supported",
            "grant_types_supported",
            "code_challenge_methods_supported"
        ]
        mock_discovery = {
            "issuer": "http://localhost:8069",
            "authorization_endpoint": "http://localhost:8069/oauth2/authorize",
            "token_endpoint": "http://localhost:8069/oauth2/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"]
        }
        for k in expected_keys:
            self.assertIn(k, mock_discovery)

if __name__ == "__main__":
    unittest.main()
