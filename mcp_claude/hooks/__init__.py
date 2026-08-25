# -*- coding: utf-8 -*-
import os
import sys
import logging
from odoo.addons.mcp_claude.bin.mcp_https_proxy import start_proxy_thread
from ..utils.crypto import generate_random_secret

_logger = logging.getLogger(__name__)

def post_load():
    try:
        active_port = start_proxy_thread()
        if active_port:
            _logger.info(f"MCP Trusted HTTPS Proxy Started Automatically on Port {active_port}")
        else:
            _logger.info("MCP HTTPS Proxy Pending: Run setup_localhost_ssl.py to activate SSL")
    except Exception as e:
        _logger.warning(f"Could not auto-start HTTPS Proxy: {e}")

def post_init_hook(env):
    """
    Executed automatically after module installation.
    Generates a cryptographically secure 256-bit random HMAC secret
    in ir.config_parameter if missing.
    """
    try:
        config_param = env['ir.config_parameter'].sudo()
        existing_secret = config_param.get_param('mcp_claude.hmac_secret')
        if not existing_secret:
            new_secret = generate_random_secret(32)
            config_param.set_param('mcp_claude.hmac_secret', new_secret)
            _logger.info("Successfully generated and saved installation HMAC secret for mcp_claude.")
        else:
            _logger.info("mcp_claude.hmac_secret already exists in ir.config_parameter.")
    except Exception as e:
        _logger.warning(f"Warning in post_init_hook during HMAC secret setup: {e}")

