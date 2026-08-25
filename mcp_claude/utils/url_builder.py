# -*- coding: utf-8 -*-
"""
Stateless URL & Endpoint Assembly Utilities for mcp_claude
Zero ORM dependencies for maximum performance and unit testability.
"""

import urllib.parse
from typing import Optional, Dict, Any

def sanitize_base_url(url: str, default_scheme: str = "http") -> str:
    """Ensure URL has scheme and no trailing slash."""
    if not url:
        return ""
    clean = str(url).strip().rstrip('/')
    if not clean.startswith(('http://', 'https://')):
        clean = f"{default_scheme}://{clean}"
    return clean

def build_endpoint_url(base_url: str, path: str, params: Optional[Dict[str, Any]] = None) -> str:
    """Build sanitized full endpoint URL with query parameters."""
    clean_base = sanitize_base_url(base_url)
    clean_path = '/' + str(path).lstrip('/')
    full_url = f"{clean_base}{clean_path}"
    if params:
        query_str = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_str:
            full_url = f"{full_url}?{query_str}"
    return full_url

def parse_url_host_scheme(url: str) -> Dict[str, Any]:
    """Parse URL into scheme, hostname, port."""
    clean = sanitize_base_url(url)
    parsed = urllib.parse.urlparse(clean)
    scheme = (parsed.scheme or 'http').lower()
    hostname = (parsed.hostname or 'localhost').lower()
    port = parsed.port or (443 if scheme == 'https' else 80)
    return {
        "scheme": scheme,
        "hostname": hostname,
        "port": port,
        "is_https": scheme == 'https'
    }
