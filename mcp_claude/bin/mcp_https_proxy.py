# -*- coding: utf-8 -*-
"""
Production Multi-Threaded HTTPS Proxy for MCP Claude
Auto-binds port 8443, handles multi-threaded SSE streaming,
and logs every incoming request from Claude Desktop.
"""

import sys
import os
import ssl
import socket
import atexit
import threading
import http.client
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 8069
DEFAULT_HTTPS_PORT = 8443
ACTIVE_HTTPS_PORT = DEFAULT_HTTPS_PORT

CERT_FILE = r"D:\odoo-mcp\certs\server.crt"
KEY_FILE = r"D:\odoo-mcp\certs\server.key"

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class ProductionHTTPSProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Explicit request logging for debugging Claude Desktop
        sys.stdout.write(f"[HTTPS PROXY] {self.command} {self.path} - {args[0]}\n")
        sys.stdout.flush()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        self._proxy_request('GET')

    def do_POST(self):
        self._proxy_request('POST')

    def _proxy_request(self, method):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        print(f"\n[>>> INCOMING CLAUDE REQUEST] {method} {self.path}")
        if body:
            print(f"    Payload: {body.decode('utf-8', errors='ignore')}")

        try:
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=30)
            headers = {k: v for k, v in self.headers.items() if k.lower() != 'host'}
            headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"
            headers['X-Forwarded-Proto'] = 'https'

            conn.request(method, self.path, body, headers)
            resp = conn.getresponse()

            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding', 'content-length'):
                    self.send_header(k, v)
            self.send_header('Access-Control-Allow-Origin', '*')

            # SSE Streaming handling
            if 'text/event-stream' in resp.getheader('Content-Type', ''):
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                print(f"[<<< SSE STREAM ESTABLISHED] HTTP {resp.status}")
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                resp_body = resp.read()
                self.send_header('Content-Length', str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
                print(f"[<<< RESPONSE SENT] HTTP {resp.status}: {resp_body.decode('utf-8', errors='ignore')[:300]}")
            conn.close()
        except Exception as e:
            print(f"[!!! PROXY ERROR] {e}")
            try:
                self.send_error(502, f"Bad Gateway: {e}")
            except Exception:
                pass

def find_available_port(start_port=8443, max_attempts=10):
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return start_port

server_instance = None

def start_proxy_thread():
    global ACTIVE_HTTPS_PORT, server_instance
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        return None

    ACTIVE_HTTPS_PORT = find_available_port(DEFAULT_HTTPS_PORT)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    server_instance = ThreadedHTTPServer(('0.0.0.0', ACTIVE_HTTPS_PORT), ProductionHTTPSProxyHandler)
    server_instance.socket = ctx.wrap_socket(server_instance.socket, server_side=True)

    t = threading.Thread(target=server_instance.serve_forever, daemon=True)
    t.start()

    atexit.register(stop_proxy)
    return ACTIVE_HTTPS_PORT

def stop_proxy():
    global server_instance
    if server_instance:
        try:
            server_instance.shutdown()
            server_instance.server_close()
        except Exception:
            pass

if __name__ == "__main__":
    start_proxy_thread()
    print(f"HTTPS Proxy Started on Port: {ACTIVE_HTTPS_PORT}")
