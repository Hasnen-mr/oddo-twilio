# -*- coding: utf-8 -*-
"""
Unit tests for stateless pure-python utilities in mcp_claude
"""

import unittest
import sys
import os
import hashlib
import base64

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.crypto import generate_random_secret, compare_digests, compute_hmac_signature, verify_pkce_challenge
from utils.url_builder import sanitize_base_url, build_endpoint_url, parse_url_host_scheme
from utils.jsonrpc import format_jsonrpc_success, format_jsonrpc_error, parse_jsonrpc_request

class TestStatelessUtils(unittest.TestCase):

    def test_crypto_utils(self):
        sec1 = generate_random_secret(32)
        sec2 = generate_random_secret(32)
        self.assertEqual(len(sec1), 64)
        self.assertTrue(compare_digests(sec1, sec1))
        self.assertFalse(compare_digests(sec1, sec2))

        sig1 = compute_hmac_signature("secret_key", "hello world")
        sig2 = compute_hmac_signature("secret_key", "hello world")
        self.assertEqual(sig1, sig2)

        # PKCE S256 test
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
        self.assertTrue(verify_pkce_challenge(verifier, challenge, "S256"))

    def test_url_builder_utils(self):
        clean_url = sanitize_base_url("odoo.zantatech.com/")
        self.assertEqual(clean_url, "http://odoo.zantatech.com")

        endpoint = build_endpoint_url("https://odoo.zantatech.com", "/mcp/v1/sse", {"token": "abc", "session_id": "s1"})
        self.assertEqual(endpoint, "https://odoo.zantatech.com/mcp/v1/sse?token=abc&session_id=s1")

        parsed = parse_url_host_scheme("https://odoo.zantatech.com:8443")
        self.assertEqual(parsed["scheme"], "https")
        self.assertEqual(parsed["hostname"], "odoo.zantatech.com")
        self.assertEqual(parsed["port"], 8443)
        self.assertTrue(parsed["is_https"])

    def test_jsonrpc_utils(self):
        parsed = parse_jsonrpc_request('{"jsonrpc": "2.0", "id": 42, "method": "tools/call", "params": {}}')
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["id"], 42)
        self.assertEqual(parsed["method"], "tools/call")

        success_payload = format_jsonrpc_success(42, {"status": "ok"})
        self.assertEqual(success_payload["jsonrpc"], "2.0")
        self.assertEqual(success_payload["result"]["status"], "ok")

        error_payload = format_jsonrpc_error(42, -32601, "Method not found")
        self.assertEqual(error_payload["error"]["code"], -32601)

if __name__ == "__main__":
    unittest.main()
