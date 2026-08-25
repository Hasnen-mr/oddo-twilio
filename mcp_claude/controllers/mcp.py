import os
import json
import time
import hashlib
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

class MCPTransportController(http.Controller):

    def _validate_api_key(self):
        try:
            import odoo
            if not getattr(request, '_env', None):
                request._env = odoo.api.Environment(request.cr, 2, request.context or {})
        except Exception:
            pass

        valid, msg, uid = request.env['mcp.security'].validate_api_key(req=request)
        return valid, msg, uid

    @http.route('/mcp/status/https', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def https_status_check(self, **kwargs):
        is_https = request.httprequest.scheme == 'https' or request.httprequest.is_secure
        cert_exists = os.path.exists(r"D:\odoo-mcp\certs\server.crt")
        return Response(json.dumps({
            "https_enabled": is_https or cert_exists,
            "scheme": request.httprequest.scheme,
            "cert_path": r"D:\odoo-mcp\certs\server.crt" if cert_exists else None
        }), status=200, headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})

    @http.route('/mcp/status/environment', type='http', auth='user', methods=['GET', 'OPTIONS'], csrf=False)
    def environment_status_check(self, **kwargs):
        headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=headers)
        override = request.params.get('override_url')
        info = request.env['mcp.tool'].sudo().get_environment_info(override_url=override)
        return Response(json.dumps(info), status=200, headers=headers)

    @http.route('/mcp/status/wizard_config', type='json', auth='user', methods=['POST'], csrf=False)
    def save_wizard_config(self, **kwargs):
        python_path = kwargs.get('python_path')
        bridge_path = kwargs.get('bridge_path')
        api_key = kwargs.get('api_key')
        server_url = kwargs.get('server_url')
        info = request.env['mcp.tool'].sudo().set_wizard_config_params(
            python_path=python_path,
            bridge_path=bridge_path,
            api_key=api_key,
            server_url=server_url
        )
        return info

    def _build_oauth_protected_resource_response(self):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Mcp-Session-Id',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Content-Type': 'application/json'
        }
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)

        scheme = request.httprequest.headers.get('X-Forwarded-Proto', request.httprequest.scheme or 'https')
        host = request.httprequest.host
        base_url = f"{scheme}://{host}".rstrip('/')
        payload = {
            "resource": f"{base_url}/mcp",
            "authorization_servers": [
                base_url
            ],
            "scopes_supported": [
                "mcp:read",
                "mcp:write"
            ]
        }
        return Response(
            json.dumps(payload, indent=2),
            status=200,
            headers=headers
        )

    @http.route([
        '/.well-known/oauth-protected-resource',
        '/.well-known/oauth-protected-resource/mcp',
        '/.well-known/oauth-protected-resource/mcp/v1/sse'
    ], type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def oauth_protected_resource_discovery(self, **kwargs):
        return self._build_oauth_protected_resource_response()

    @http.route([
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-authorization-server/mcp'
    ], type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def oauth_authorization_server_metadata(self, **kwargs):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Mcp-Session-Id',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Content-Type': 'application/json'
        }
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)

        scheme = request.httprequest.headers.get('X-Forwarded-Proto', request.httprequest.scheme or 'https')
        host = request.httprequest.host
        base_url = f"{scheme}://{host}".rstrip('/')
        payload = {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/mcp/oauth/authorize",
            "token_endpoint": f"{base_url}/mcp/oauth/token",
            "registration_endpoint": f"{base_url}/oauth2/register",
            "revocation_endpoint": f"{base_url}/mcp/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            "scopes_supported": ["mcp:read", "mcp:write"]
        }
        return Response(json.dumps(payload, indent=2), status=200, headers=headers)

    @http.route(['/mcp', '/mcp/v1/sse'], type='http', auth='none', methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def sse_stream(self, **kwargs):
        # Handle POST as Streamable HTTP JSON-RPC request
        if request.httprequest.method == 'POST':
            content_type = request.httprequest.headers.get('Content-Type', '')
            raw_data = request.httprequest.get_data(as_text=True) or ''
            if 'application/json' in content_type or (raw_data and raw_data.strip().startswith('{')):
                return self.handle_messages(**kwargs)

        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Mcp-Session-Id',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8'
        }

        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=headers)

        valid, msg, auth_uid = self._validate_api_key()
        if not valid:
            host_hdr = request.httprequest.headers.get('Host', 'odoo.localhost:8443')
            metadata_url = f"https://{host_hdr}/.well-known/oauth-protected-resource"
            unauth_headers = {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'WWW-Authenticate': f'Bearer resource_metadata="{metadata_url}"'
            }
            return Response(json.dumps({"error": msg}), status=401, headers=unauth_headers)

        auth_header = request.httprequest.headers.get('Authorization', '')
        raw_token = None
        if auth_header and auth_header.startswith('Bearer '):
            raw_token = auth_header.split(' ', 1)[1].strip()
        if not raw_token:
            raw_token = kwargs.get('token') or request.params.get('token') or 'mcp_live_default'

        session_id = request.httprequest.headers.get('Mcp-Session-Id') or f"sess_claude_{hashlib.md5((raw_token + request.httprequest.remote_addr).encode('utf-8')).hexdigest()[:8]}"

        try:
            request.env['mcp.session'].sudo().record_heartbeat(
                session_token=session_id,
                client_name="Claude Desktop",
                transport="remote_https",
                method="sse_connect",
                user_id=auth_uid
            )
        except Exception as e:
            _logger.warning(f"SSE Heartbeat recording warning: {e}")

        scheme = request.httprequest.headers.get('X-Forwarded-Proto', request.httprequest.scheme or 'https')
        host = request.httprequest.host
        base_url = f"{scheme}://{host}".rstrip('/')
        endpoint_uri = f"{base_url}/mcp/v1/messages?session_id={session_id}&token={raw_token}"

        _logger.info(f"Persistent SSE Stream Established for Claude session: {session_id}")

        def stream_generator():
            yield f"event: endpoint\ndata: {endpoint_uri}\n\n".encode('utf-8')
            count = 0
            while count < 120:
                time.sleep(15)
                count += 1
                try:
                    import odoo
                    with odoo.registry(request.db).cursor() as cr:
                        env = odoo.api.Environment(cr, auth_uid or 2, {})
                        env['mcp.session'].sudo().record_heartbeat(
                            session_token=session_id,
                            client_name="Claude Desktop",
                            transport="remote_https",
                            method="sse_ping",
                            user_id=auth_uid
                        )
                except Exception:
                    pass
                yield f": ping {count}\n\n".encode('utf-8')

        return Response(stream_generator(), status=200, headers=headers)

    @http.route('/mcp/status/refresh', type='json', auth='user', methods=['POST'], csrf=False)
    def hard_session_refresh_endpoint(self, **kwargs):
        _logger.info("Dashboard requested hard MCP session refresh")
        request.env['mcp.session'].sudo().action_hard_session_refresh()
        request.env['mcp.tool'].sudo().reload_builtin_tools()
        return request.env['mcp.tool'].sudo().get_claude_connection_status()

    @http.route('/mcp/v1/messages', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def handle_messages(self, **kwargs):
        headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=headers)

        try:
            import odoo
            if not getattr(request, '_env', None):
                request._env = odoo.api.Environment(request.cr, 2, request.context or {})
        except Exception:
            pass

        valid, auth_msg, auth_uid = self._validate_api_key()
        if not valid:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": auth_msg}}
            return Response(json.dumps(err_resp), status=401, headers=headers)

        try:
            raw_data = request.httprequest.get_data(as_text=True)
            body = json.loads(raw_data) if raw_data else (kwargs or {})
        except Exception:
            body = kwargs or {}

        req_id = body.get('id') if isinstance(body, dict) else None
        method = body.get('method') if isinstance(body, dict) else None

        # Extract stable session ID
        auth_header = request.httprequest.headers.get('Authorization', '')
        session_hdr = request.httprequest.headers.get('Mcp-Session-Id') or request.params.get('session_id') or request.params.get('token') or request.params.get('api_key')

        if not session_hdr and auth_header and auth_header.startswith('Bearer '):
            raw_t = auth_header.split(' ', 1)[1].strip()
            session_hdr = f"sess_bearer_{hashlib.md5(raw_t.encode('utf-8')).hexdigest()[:8]}"

        if not session_hdr:
            client_ip = request.httprequest.remote_addr or "127.0.0.1"
            session_hdr = f"sess_claude_{hashlib.md5(client_ip.encode('utf-8')).hexdigest()[:8]}"

        is_sec = request.httprequest.is_secure or request.httprequest.scheme == 'https'
        trans = "remote_https" if ('mcp_access_' in auth_header or is_sec) else "stdio_bridge"

        # Multi-worker persistent session heartbeat recording (best effort, isolated cursor)
        try:
            _logger.info(f"MCP Request Received: method='{method}', session_token='{session_hdr}', req_id={req_id}, user_id={auth_uid}")
            request.env['mcp.session'].sudo().record_heartbeat(
                session_token=session_hdr,
                client_name="Claude Desktop",
                transport=trans,
                method=method or "tools/list",
                user_id=auth_uid
            )
        except Exception as e:
            _logger.warning(f"Heartbeat controller wrapper exception (safely caught): {e}")

        if req_id is None and method and method.startswith('notifications/'):
            return Response("", status=204, headers=headers)

        # Propagate authenticated user identity strictly via with_user() without session mutation
        response_dict = request.env['mcp.dispatcher'].with_user(auth_uid).dispatch(body)
        if response_dict is None:
            return Response("", status=204, headers=headers)

        return Response(json.dumps(response_dict), status=200, headers=headers)
