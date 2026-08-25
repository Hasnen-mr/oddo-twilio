# -*- coding: utf-8 -*-
"""
mcp.environment Service (AbstractModel)
Single source of truth for runtime environment detection, reverse-proxy inspection,
network subnet classification, and capability payload generation.
Idiomatic Odoo AbstractModel service pattern.
"""

import ipaddress
import logging
from odoo import models, api
from ..utils.url_builder import sanitize_base_url, parse_url_host_scheme

_logger = logging.getLogger(__name__)

class MCPEnvironmentService(models.AbstractModel):
    _name = 'mcp.environment'
    _description = 'MCP Runtime Environment Service'

    @api.model
    def get_info(self, override_url=None):
        """
        Inspect runtime deployment environment.
        Prioritizes active HTTP request context (with reverse proxy headers) over web.base.url.
        Returns normalized environment classification and capabilities dict.
        """
        req = self.env.get('request') if hasattr(self.env, 'get') else None
        base_url = None
        scheme = None
        forwarded_proto = None
        forwarded_host = None

        if override_url:
            base_url = str(override_url).strip()
        elif req and hasattr(req, 'httprequest') and req.httprequest:
            httpreq = req.httprequest
            forwarded_proto = httpreq.headers.get('X-Forwarded-Proto') or httpreq.headers.get('X-Forwarded-Scheme')
            forwarded_host = httpreq.headers.get('X-Forwarded-Host')

            if forwarded_proto:
                scheme = forwarded_proto.split(',')[0].strip().lower()
            elif httpreq.is_secure or httpreq.scheme == 'https':
                scheme = 'https'
            else:
                scheme = (httpreq.scheme or 'http').lower()

            if forwarded_host:
                host_str = forwarded_host.split(',')[0].strip()
                base_url = f"{scheme}://{host_str}"
            else:
                host_url = getattr(httpreq, 'host_url', None) or getattr(httpreq, 'url_root', None)
                if host_url:
                    base_url = host_url

        if not base_url:
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "http://localhost:8069"

        base_url = sanitize_base_url(base_url, default_scheme=scheme or 'http')
        parsed = parse_url_host_scheme(base_url)
        scheme = scheme or parsed['scheme']
        hostname = parsed['hostname']
        port = parsed['port']

        # Localhost & Private Subnet Inspection
        is_localhost = False
        if hostname in ['localhost', '127.0.0.1', '0.0.0.0', '::1'] or hostname.endswith('.local'):
            is_localhost = True
        else:
            try:
                ip_obj = ipaddress.ip_address(hostname)
                if ip_obj.is_private or ip_obj.is_loopback:
                    is_localhost = True
            except ValueError:
                if hostname.startswith(('10.', '192.168.')):
                    is_localhost = True
                elif hostname.startswith('172.'):
                    parts = hostname.split('.')
                    if len(parts) >= 2 and parts[1].isdigit():
                        octet2 = int(parts[1])
                        if 16 <= octet2 <= 31:
                            is_localhost = True

        is_https = (scheme == 'https')

        if is_localhost:
            env_code = "local"
            badge_label = "🔵 Local Development"
            badge_class = "bg-info"
            supports_direct = False
        elif is_https:
            env_code = "production"
            badge_label = "🟢 HTTPS Enabled"
            badge_class = "bg-success"
            supports_direct = True
        else:
            env_code = "remote-http"
            badge_label = "🟡 Remote HTTP"
            badge_class = "bg-warning"
            supports_direct = False

        return {
            "base_url": base_url,
            "scheme": scheme,
            "hostname": hostname,
            "port": port,
            "is_https": is_https,
            "is_localhost": is_localhost,
            "env_code": env_code,
            "badge_label": badge_label,
            "badge_class": badge_class,
            "supports_direct_url": supports_direct,
            "capabilities": {
                "tools": True,
                "resources": True,
                "prompts": True,
                "sse": True,
                "oauth": True,
                "direct_connection": supports_direct
            }
        }
