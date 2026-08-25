# -*- coding: utf-8 -*-
import logging
import json
import secrets
import hashlib
import base64
import time
import datetime
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

def _base64url_encode(input_bytes):
    return base64.urlsafe_b64encode(input_bytes).rstrip(b'=').decode('utf-8')

class MCPOAuthController(http.Controller):

    @http.route('/oauth2/register', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    @http.route('/mcp/oauth/register', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def register(self, **kwargs):
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=headers)

        try:
            raw_data = request.httprequest.get_data(as_text=True)
            data = json.loads(raw_data) if raw_data else kwargs
        except Exception:
            data = kwargs

        client_name = data.get('client_name') or data.get('client_name_default') or 'Claude Desktop App'
        redirect_uris = data.get('redirect_uris') or []
        if isinstance(redirect_uris, str):
            redirect_uris = [redirect_uris]

        primary_redirect_uri = redirect_uris[0] if redirect_uris else 'claude://claude.ai/mcp-auth-callback/sdk'
        redirect_uris_str = ",".join(redirect_uris) if redirect_uris else primary_redirect_uri

        raw_secret, client_id = request.env['mcp.oauth.client'].sudo().create_oauth_client(
            name=client_name,
            redirect_uri=primary_redirect_uri
        )
        client_rec = request.env['mcp.oauth.client'].sudo().browse(client_id)
        if redirect_uris_str:
            client_rec.sudo().write({'redirect_uris': redirect_uris_str})

        response_payload = {
            "client_id": client_rec.client_id,
            "client_secret": raw_secret,
            "client_name": client_rec.name,
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0,
            "redirect_uris": redirect_uris or [primary_redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"
        }

        _logger.info(f"Registered new Dynamic OAuth Client: {client_rec.client_id} ({client_name})")
        return Response(json.dumps(response_payload, indent=2), status=201, headers=headers)

    @http.route('/mcp/oauth/authorize', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def authorize(self, **kwargs):
        headers = {'Access-Control-Allow-Origin': '*'}
        
        client_id = kwargs.get('client_id')
        redirect_uri = kwargs.get('redirect_uri')
        state = kwargs.get('state', '')
        response_type = kwargs.get('response_type', 'code')
        code_challenge = kwargs.get('code_challenge')
        code_challenge_method = kwargs.get('code_challenge_method', 'S256')
        scope = kwargs.get('scope', 'mcp:read mcp:write')

        if not client_id:
            return Response('<html><body><h3>OAuth Error: Missing client_id parameter</h3></body></html>', status=400, headers=headers)

        client_rec = request.env['mcp.oauth.client'].sudo().search([('client_id', '=', client_id), ('active', '=', True)], limit=1)
        if not client_rec:
            return Response(f'<html><body><h3>OAuth Error: Invalid client_id {client_id}</h3></body></html>', status=400, headers=headers)

        target_redirect_uri = redirect_uri or client_rec.redirect_uri or 'claude://claude.ai/mcp-auth-callback/sdk'
        if target_redirect_uri.startswith('/'):
            scheme = request.httprequest.headers.get('X-Forwarded-Proto', request.httprequest.scheme or 'https')
            host = request.httprequest.host
            base_url = f"{scheme}://{host}".rstrip('/')
            target_redirect_uri = f"{base_url}{target_redirect_uri}"

        # Security Check: Require authenticated Odoo user session
        if not request.env.user or request.env.user._is_public():
            if request.httprequest.method == 'POST':
                return Response(
                    json.dumps({"error": "unauthorized", "error_description": "User must be authenticated to authorize OAuth access."}),
                    status=401,
                    headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
                )
            # For GET requests, redirect to standard Odoo login page
            current_path = request.httprequest.full_path or request.httprequest.path
            login_url = f"/web/login?redirect={urllib.parse.quote(current_path)}"
            return Response(status=302, headers=[('Location', login_url), ('Access-Control-Allow-Origin', '*')])

        user_rec = request.env.user

        # If authenticated user submits consent form
        if request.httprequest.method == 'POST':
            code_rec = request.env['mcp.oauth.code'].sudo().create_code(
                client_rec=client_rec,
                user_rec=user_rec,
                redirect_uri=target_redirect_uri,
                scope=scope,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method
            )

            sep = '&' if '?' in target_redirect_uri else '?'
            redirect_url = f"{target_redirect_uri}{sep}code={code_rec.code}"
            if state:
                redirect_url += f"&state={state}"

            _logger.info(f"OAuth Authorization Code Issued: {code_rec.code} for Client {client_id} (User: {user_rec.login}) -> {redirect_url}")
            return Response(status=302, headers=[('Location', redirect_url), ('Access-Control-Allow-Origin', '*')])

        # Render HTML Consent & Login Page
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Odoo MCP Authorization</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card {{ background: #1e293b; padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 380px; text-align: center; border: 1px solid #334155; }}
                h2 {{ color: #38bdf8; margin-top: 0; }}
                p {{ color: #94a3b8; font-size: 0.95rem; }}
                .btn {{ background: #0284c7; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: bold; cursor: pointer; width: 100%; margin-top: 1rem; font-size: 1rem; }}
                .btn:hover {{ background: #0369a1; }}
                .client-box {{ background: #0f172a; padding: 0.75rem; border-radius: 0.5rem; margin: 1rem 0; font-family: monospace; font-size: 0.85rem; color: #cbd5e1; word-break: break-all; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Odoo MCP Connect</h2>
                <p>Allow <strong>{client_rec.name}</strong> to connect to your Odoo Instance?</p>
                <div class="client-box">Client ID: {client_id}</div>
                <form method="POST" action="/mcp/oauth/authorize">
                    <input type="hidden" name="client_id" value="{client_id}"/>
                    <input type="hidden" name="redirect_uri" value="{target_redirect_uri}"/>
                    <input type="hidden" name="state" value="{state}"/>
                    <input type="hidden" name="code_challenge" value="{code_challenge or ''}"/>
                    <input type="hidden" name="code_challenge_method" value="{code_challenge_method}"/>
                    <input type="hidden" name="scope" value="{scope}"/>
                    <button type="submit" class="btn">Authorize Connection</button>
                </form>
            </div>
        </body>
        </html>
        """
        return Response(html_content, status=200, headers={'Content-Type': 'text/html', 'Access-Control-Allow-Origin': '*'})

    @http.route('/mcp/oauth/token', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def token(self, **kwargs):
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Cache-Control': 'no-store',
            'Pragma': 'no-cache',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
        if request.httprequest.method == 'OPTIONS':
            return Response(status=204, headers=headers)

        data = {}
        # Parse HTTP Authorization Basic header for client_secret_basic authentication
        auth_header = request.httprequest.headers.get('Authorization')
        if auth_header and auth_header.startswith('Basic '):
            try:
                b64_val = auth_header.split(' ', 1)[1].strip()
                decoded_str = base64.b64decode(b64_val).decode('utf-8')
                if ':' in decoded_str:
                    c_id, c_secret = decoded_str.split(':', 1)
                    data['client_id'] = c_id
                    data['client_secret'] = c_secret
            except Exception:
                pass

        if request.httprequest.form:
            data.update(request.httprequest.form.to_dict())
        try:
            raw_data = request.httprequest.get_data(as_text=True)
            if raw_data and raw_data.strip().startswith('{'):
                data.update(json.loads(raw_data))
        except Exception:
            pass
        if kwargs:
            data.update(kwargs)
        if request.httprequest.args:
            data.update(request.httprequest.args.to_dict())

        grant_type = data.get('grant_type')
        client_id = data.get('client_id')
        code = data.get('code')
        code_verifier = data.get('code_verifier')
        redirect_uri = data.get('redirect_uri')
        refresh_token_param = data.get('refresh_token')

        _logger.info(f"OAuth Token Exchange Requested: grant_type={grant_type}, client_id={client_id}, code={code[:10] if code else None}")

        if grant_type == 'authorization_code':
            if not code:
                return Response(json.dumps({"error": "invalid_request", "error_description": "Missing code parameter"}), status=400, headers=headers)

            code_rec = request.env['mcp.oauth.code'].sudo().search([('code', '=', code)], limit=1)
            if not code_rec:
                return Response(json.dumps({"error": "invalid_grant", "error_description": "Invalid or non-existent authorization code"}), status=400, headers=headers)

            if code_rec.used:
                # If token was issued less than 30s ago, return existing token to handle network retries cleanly
                existing_token = request.env['mcp.oauth.token'].sudo().search([('client_id', '=', code_rec.client_id.id), ('user_id', '=', code_rec.user_id.id), ('revoked', '=', False)], limit=1, order='id desc')
                if existing_token and existing_token.expires_at > fields.Datetime.now():
                    _logger.info(f"Returning existing active token for re-sent code {code[:10]}")
                    return Response(json.dumps({
                        "access_token": existing_token.access_token,
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "refresh_token": existing_token.refresh_token,
                        "scope": code_rec.scope
                    }, indent=2), status=200, headers=headers)

                return Response(json.dumps({"error": "invalid_grant", "error_description": "Authorization code has already been used"}), status=400, headers=headers)

            if code_rec.expires_at and code_rec.expires_at < fields.Datetime.now():
                code_rec.sudo().write({'used': True})
                return Response(json.dumps({"error": "invalid_grant", "error_description": "Authorization code has expired"}), status=400, headers=headers)

            # PKCE Verification if code_challenge was provided
            if code_rec.code_challenge:
                if not code_verifier:
                    return Response(json.dumps({"error": "invalid_request", "error_description": "Missing PKCE code_verifier"}), status=400, headers=headers)

                if code_rec.code_challenge_method == 'S256':
                    computed_challenge = _base64url_encode(hashlib.sha256(code_verifier.encode('utf-8')).digest())
                    if not secrets.compare_digest(computed_challenge, code_rec.code_challenge):
                        _logger.warning(f"PKCE mismatch: computed={computed_challenge}, stored={code_rec.code_challenge}")
                        return Response(json.dumps({"error": "invalid_grant", "error_description": "PKCE code_verifier mismatch"}), status=400, headers=headers)

            # Mark code as consumed
            code_rec.sudo().write({'used': True})

            access_token = f"mcp_access_{secrets.token_urlsafe(32)}"
            refresh_token = f"mcp_refresh_{secrets.token_urlsafe(32)}"
            expires_in = 3600
            expires_at = fields.Datetime.now() + datetime.timedelta(seconds=expires_in)

            token_rec = request.env['mcp.oauth.token'].sudo().create({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'client_id': code_rec.client_id.id,
                'user_id': code_rec.user_id.id,
                'code_challenge': code_rec.code_challenge,
                'code_challenge_method': code_rec.code_challenge_method,
                'expires_at': expires_at,
                'revoked': False
            })

            _logger.info(f"OAuth Tokens Successfully Issued for User {code_rec.user_id.name} (Client: {code_rec.client_id.client_id})")

            return Response(json.dumps({
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "scope": code_rec.scope
            }, indent=2), status=200, headers=headers)

        elif grant_type == 'refresh_token':
            if not refresh_token_param:
                return Response(json.dumps({"error": "invalid_request", "error_description": "Missing refresh_token parameter"}), status=400, headers=headers)

            old_token_rec = request.env['mcp.oauth.token'].sudo().search([('refresh_token', '=', refresh_token_param), ('revoked', '=', False)], limit=1)
            if not old_token_rec:
                return Response(json.dumps({"error": "invalid_grant", "error_description": "Invalid or revoked refresh token"}), status=400, headers=headers)

            # Revoke old token pair
            old_token_rec.sudo().write({'revoked': True})

            access_token = f"mcp_access_{secrets.token_urlsafe(32)}"
            new_refresh_token = f"mcp_refresh_{secrets.token_urlsafe(32)}"
            expires_in = 3600
            expires_at = fields.Datetime.now() + datetime.timedelta(seconds=expires_in)

            request.env['mcp.oauth.token'].sudo().create({
                'access_token': access_token,
                'refresh_token': new_refresh_token,
                'client_id': old_token_rec.client_id.id,
                'user_id': old_token_rec.user_id.id,
                'expires_at': expires_at,
                'revoked': False
            })

            return Response(json.dumps({
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": new_refresh_token
            }, indent=2), status=200, headers=headers)

        return Response(json.dumps({"error": "unsupported_grant_type", "error_description": f"Unsupported grant_type {grant_type}"}), status=400, headers=headers)

    @http.route('/mcp/oauth/revoke', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def revoke(self, **kwargs):
        headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        token_param = kwargs.get('token')
        if token_param:
            token_recs = request.env['mcp.oauth.token'].sudo().search(['|', ('access_token', '=', token_param), ('refresh_token', '=', token_param)])
            token_recs.sudo().write({'revoked': True})
        return Response(json.dumps({"status": "revoked"}), status=200, headers=headers)

    @http.route([
        '/api/mcp/auth_callback',
        '/mcp/oauth/callback',
        '/mcp/oauth/auth_callback'
    ], type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def auth_callback(self, **kwargs):
        code = kwargs.get('code')
        state = kwargs.get('state', '')
        error = kwargs.get('error')
        error_description = kwargs.get('error_description', '')

        _logger.info(f"OAuth Callback Invoked: code={code}, state={state}, error={error}")

        if error:
            html_error = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Odoo MCP Authorization Error</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #1e293b; padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 420px; text-align: center; border: 1px solid #ef4444; }}
                    h2 {{ color: #f87171; margin-top: 0; }}
                    p {{ color: #94a3b8; font-size: 0.95rem; }}
                    .error-box {{ background: #450a0a; padding: 0.75rem; border-radius: 0.5rem; margin: 1rem 0; font-family: monospace; font-size: 0.85rem; color: #fca5a5; word-break: break-all; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Authorization Failed</h2>
                    <p>The OAuth authorization request was declined or failed.</p>
                    <div class="error-box">Error: {error}<br/>{error_description}</div>
                </div>
            </body>
            </html>
            """
            return Response(html_error, status=400, headers={'Content-Type': 'text/html', 'Access-Control-Allow-Origin': '*'})

        code_display = f"{code[:12]}..." if code else "Granted"

        html_success = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Odoo MCP Authorization Successful</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card {{ background: #1e293b; padding: 2.5rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 440px; text-align: center; border: 1px solid #22c55e; }}
                .icon {{ font-size: 3rem; margin-bottom: 0.5rem; }}
                h2 {{ color: #4ade80; margin-top: 0; margin-bottom: 0.5rem; }}
                p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }}
                .code-box {{ background: #0f172a; padding: 0.75rem; border-radius: 0.5rem; margin: 1rem 0; font-family: monospace; font-size: 0.85rem; color: #38bdf8; word-break: break-all; border: 1px solid #334155; }}
                .btn {{ background: #22c55e; color: #052e16; border: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: bold; cursor: pointer; width: 100%; margin-top: 1rem; font-size: 1rem; text-decoration: none; display: inline-block; box-sizing: border-box; }}
                .btn:hover {{ background: #16a34a; }}
                .subtext {{ font-size: 0.8rem; color: #64748b; margin-top: 1rem; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">🟢</div>
                <h2>Authorization Successful</h2>
                <p>Your Odoo MCP Server has successfully authorized <strong>Claude Desktop</strong>.</p>
                <div class="code-box">Auth Code: {code_display}</div>
                <a href="claude://claude.ai/mcp-auth-callback/sdk?code={code or ''}&state={state or ''}" class="btn">Return to Claude Desktop</a>
                <p class="subtext">You can now close this browser tab and return to Claude Desktop.</p>
            </div>
            <script>
                if ('{code}' && '{code}' !== 'None') {{
                    setTimeout(function() {{
                        window.location.href = 'claude://claude.ai/mcp-auth-callback/sdk?code={code}&state={state}';
                    }}, 800);
                }}
            </script>
        </body>
        </html>
        """
        return Response(html_success, status=200, headers={'Content-Type': 'text/html', 'Access-Control-Allow-Origin': '*'})
