#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Claude stdio-to-HTTP Bridge
Communicates with Claude Desktop via stdin/stdout and forwards JSON-RPC requests to Odoo HTTP server.
"""

import sys
import json
import argparse
import logging
import urllib.request
import urllib.error

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='[mcp-bridge] %(asctime)s - %(levelname)s - %(message)s'
)

def parse_args():
    parser = argparse.ArgumentParser(description="MCP Claude stdio Bridge")
    parser.add_argument("--server", default="http://localhost:8069", help="Odoo server URL base")
    parser.add_argument("--api-key", default="mcp_live_default", help="Bearer API key for MCP authentication")
    return parser.parse_args()

def send_http_request(server_url, api_key, payload):
    endpoint = server_url.rstrip('/') + '/mcp/v1/messages'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=data,
                headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'Mcp-Session-Id': 'sess_stdio_claude_desktop'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode('utf-8')
            if not res_body or response.status == 204:
                return None
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        logging.error(f"HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        logging.error(f"Network error forwarding to Odoo: {e}")
        return None

def main():
    args = parse_args()
    logging.info(f"Starting MCP stdio bridge -> Forwarding to {args.server}")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line_str = line.strip()
            if not line_str:
                continue

            try:
                payload = json.loads(line_str)
            except json.JSONDecodeError as e:
                continue

            # If request is a notification (no 'id'), do not output a response to stdout
            req_id = payload.get("id")
            response = send_http_request(args.server, args.api_key, payload)
            
            if req_id is not None and response:
                out_line = json.dumps(response)
                sys.stdout.write(out_line + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == "__main__":
    main()
