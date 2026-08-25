# -*- coding: utf-8 -*-
"""
Full System Runtime Validation Script for mcp_claude
Executes real HTTP requests, JSON-RPC 2.0 protocol calls, and live server endpoints.
"""

import sys
import os
import json
import urllib.request
import urllib.error
import time

BASE_URL = "http://localhost:8069"
API_KEY = "mcp_live_default"

def log_step(step_num, title, cmd, output, status):
    print(f"\n{'='*70}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*70}")
    print(f"Command/Action: {cmd}")
    print(f"Status: {status}")
    print(f"Output:\n{output[:1000]}")
    return status == "PASS"

def run_runtime_validation():
    results = []
    
    # 1. Health Endpoint
    try:
        url = f"{BASE_URL}/mcp/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            pass_1 = log_step(1, "Confirm /mcp/health Endpoint", f"GET {url}", f"HTTP {code}: {body}", "PASS" if code == 200 and "online" in body else "FAIL")
            results.append(("Health Endpoint", pass_1))
    except Exception as e:
        log_step(1, "Confirm /mcp/health Endpoint", f"GET {BASE_URL}/mcp/health", str(e), "FAIL")
        results.append(("Health Endpoint", False))

    # 2. OAuth Discovery Metadata Endpoint
    try:
        url = f"{BASE_URL}/.well-known/oauth-authorization-server"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            pass_2 = log_step(2, "Confirm OAuth Discovery Metadata", f"GET {url}", f"HTTP {code}: {body}", "PASS" if code == 200 and "authorization_endpoint" in body else "FAIL")
            results.append(("OAuth Discovery", pass_2))
    except Exception as e:
        log_step(2, "Confirm OAuth Discovery Metadata", f"GET {url}", str(e), "FAIL")
        results.append(("OAuth Discovery", False))

    # 3. /mcp/v1/messages POST initialize
    try:
        url = f"{BASE_URL}/mcp/v1/messages"
        payload = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "RuntimeValidator", "version": "1.0.0"}
            }
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            res_json = json.loads(body)
            pass_3 = log_step(3, "Confirm JSON-RPC initialize Method", f"POST {url} with initialize", f"HTTP {code}: {body}", "PASS" if code == 200 and res_json.get("result", {}).get("protocolVersion") == "2024-11-05" else "FAIL")
            results.append(("JSON-RPC initialize", pass_3))
    except Exception as e:
        log_step(3, "Confirm JSON-RPC initialize Method", f"POST {url} with initialize", str(e), "FAIL")
        results.append(("JSON-RPC initialize", False))

    # 4. JSON-RPC ping
    try:
        url = f"{BASE_URL}/mcp/v1/messages"
        payload = {"jsonrpc": "2.0", "id": 102, "method": "ping", "params": {}}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            res_json = json.loads(body)
            pass_4 = log_step(4, "Confirm JSON-RPC ping Method", f"POST {url} with ping", f"HTTP {code}: {body}", "PASS" if code == 200 and res_json.get("id") == 102 else "FAIL")
            results.append(("JSON-RPC ping", pass_4))
    except Exception as e:
        log_step(4, "Confirm JSON-RPC ping Method", f"POST {url} with ping", str(e), "FAIL")
        results.append(("JSON-RPC ping", False))

    # 5. JSON-RPC tools/list
    try:
        url = f"{BASE_URL}/mcp/v1/messages"
        payload = {"jsonrpc": "2.0", "id": 103, "method": "tools/list", "params": {}}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            res_json = json.loads(body)
            tools = res_json.get("result", {}).get("tools", [])
            pass_5 = log_step(5, "Confirm JSON-RPC tools/list Method", f"POST {url} with tools/list", f"HTTP {code}: Returned {len(tools)} tools", "PASS" if code == 200 and isinstance(tools, list) else "FAIL")
            results.append(("JSON-RPC tools/list", pass_5))
    except Exception as e:
        log_step(5, "Confirm JSON-RPC tools/list Method", f"POST {url} with tools/list", str(e), "FAIL")
        results.append(("JSON-RPC tools/list", False))

    # 6. JSON-RPC tools/call (Execute real tool)
    try:
        url = f"{BASE_URL}/mcp/v1/messages"
        payload = {
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "list_dashboards",
                "arguments": {}
            }
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            res_json = json.loads(body)
            result = res_json.get("result", {})
            pass_6 = log_step(6, "Confirm JSON-RPC tools/call Real Execution", f"POST {url} with tools/call list_dashboards", f"HTTP {code}: {body}", "PASS" if code == 200 and "result" in res_json else "FAIL")
            results.append(("JSON-RPC tools/call", pass_6))
    except Exception as e:
        log_step(6, "Confirm JSON-RPC tools/call Real Execution", f"POST {url} with tools/call list_dashboards", str(e), "FAIL")
        results.append(("JSON-RPC tools/call", False))

    # 7. Environment Status API
    try:
        url = f"{BASE_URL}/mcp/status/environment"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {API_KEY}'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            code = resp.status
            res_json = json.loads(body)
            pass_7 = log_step(7, "Confirm Environment Status Endpoint", f"GET {url}", f"HTTP {code}: {body}", "PASS" if code == 200 and "environment" in res_json else "FAIL")
            results.append(("Environment API", pass_7))
    except Exception as e:
        log_step(7, "Confirm Environment Status Endpoint", f"GET {url}", str(e), "FAIL")
        results.append(("Environment API", False))

    # Summary Matrix
    print("\n" + "="*70)
    print("FULL RUNTIME VALIDATION SUMMARY MATRIX")
    print("="*70)
    all_passed = True
    for title, passed in results:
        status_str = "🟢 PASS" if passed else "🔴 FAIL"
        print(f" - {title:35s}: {status_str}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("OVERALL RESULT: ALL RUNTIME CHECKS PASSED SUCCESSFULLY (100% OPERATIONAL)")
    else:
        print("OVERALL RESULT: SOME CHECKS FAILED - REVIEW LOGS ABOVE")
    print("="*70)

if __name__ == "__main__":
    run_runtime_validation()
