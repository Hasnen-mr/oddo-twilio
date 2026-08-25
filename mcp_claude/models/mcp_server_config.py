# -*- coding: utf-8 -*-
import logging
import requests
from odoo import models, fields, api
from odoo.addons.mcp_claude.bin.mcp_https_proxy import start_proxy_thread

_logger = logging.getLogger(__name__)

class MCPServerConfig(models.Model):
    def _register_hook(self):
        res = super()._register_hook()
        try:
            active_port = start_proxy_thread()
            if active_port:
                _logger.info(f"MCP Trusted HTTPS Proxy Started Automatically on Port {active_port}")
        except Exception as e:
            _logger.warning(f"HTTPS Proxy auto-start notice: {e}")
        return res

    _name = 'mcp.server.config'
    _description = 'MCP Server Configuration'

    name = fields.Char(string="Configuration Name", default="Default MCP Settings", required=True)
    profile = fields.Selection([
        ('development', 'Development'),
        ('testing', 'Testing'),
        ('production', 'Production')
    ], string="Configuration Profile", default='development', required=True)

    ai_provider = fields.Selection([
        ('claude', 'Anthropic Claude'),
        ('openai', 'OpenAI (GPT-4o)')
    ], string="Active AI Provider", default='claude', required=True, help="Select active LLM engine for conversation & tool orchestration.")

    claude_api_key = fields.Char(
        string="Anthropic API Key",
        help="Enter your Anthropic API key to enable Claude-powered responses and MCP tool execution. Stored server-side."
    )

    openai_api_key = fields.Char(
        string="OpenAI API Key",
        help="Enter your OpenAI API key (sk-proj-... or sk-...). Stored server-side and never sent to browser or logs."
    )

    openai_model = fields.Selection([
        ('gpt-4o', 'GPT-4o (Omnimodal Flagship)'),
        ('gpt-4o-mini', 'GPT-4o Mini (Fast & Efficient)'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo')
    ], string="OpenAI Model", default='gpt-4o', required=True)

    enable_tools = fields.Boolean(string="Enable Tools", default=True)
    enable_resources = fields.Boolean(string="Enable Resources", default=True)
    enable_prompts = fields.Boolean(string="Enable Prompts", default=False)
    enable_oauth = fields.Boolean(string="Enable OAuth 2.0", default=True)
    enable_api_keys = fields.Boolean(string="Enable API Keys", default=True)

    enable_twilio_dialer = fields.Boolean(string="Enable Twilio Dialer", default=False, help="Enable Twilio Power Dialer third-party integration.")
    twilio_caller_number = fields.Char(string="Caller / From Number", help="Caller ID used for outbound Twilio calls. If left empty, defaults to canonical Twilio module configuration.")

    default_token_ttl = fields.Integer(string="Token TTL (Seconds)", default=3600)
    rate_limit_rpm = fields.Integer(string="Max Requests Per Minute", default=120)

    @api.model
    def get_active_provider_name(self):
        """Returns the active provider key ('claude' or 'openai')."""
        xml_rec = self.env.ref("mcp_claude.mcp_server_config_default", raise_if_not_found=False)
        if xml_rec and xml_rec.ai_provider:
            return xml_rec.ai_provider
        config = self.sudo().search([], limit=1)
        return config.ai_provider if config and config.ai_provider else "claude"

    @api.model
    def get_claude_api_key(self):
        """Retrieve Anthropic API key securely from canonical mcp.server.config model, system parameters, or environment."""
        xml_rec = self.env.ref("mcp_claude.mcp_server_config_default", raise_if_not_found=False)
        if xml_rec and xml_rec.claude_api_key:
            return xml_rec.claude_api_key

        config = self.sudo().search([('claude_api_key', '!=', False)], limit=1)
        if config and config.claude_api_key:
            return config.claude_api_key

        param_key = self.env['ir.config_parameter'].sudo().get_param('mcp_claude.claude_api_key', None)
        if param_key:
            return param_key

        import os
        return os.environ.get("ANTHROPIC_API_KEY", None)

    @api.model
    def get_openai_api_key(self):
        """Retrieve OpenAI API key securely from canonical mcp.server.config model, system parameters, or environment."""
        xml_rec = self.env.ref("mcp_claude.mcp_server_config_default", raise_if_not_found=False)
        if xml_rec and xml_rec.openai_api_key:
            return xml_rec.openai_api_key

        config = self.sudo().search([('openai_api_key', '!=', False)], limit=1)
        if config and config.openai_api_key:
            return config.openai_api_key

        param_key = self.env['ir.config_parameter'].sudo().get_param('mcp_claude.openai_api_key', None)
        if param_key:
            return param_key

        import os
        return os.environ.get("OPENAI_API_KEY", None)

    @api.model
    def get_openai_model(self):
        """Retrieve OpenAI Model setting."""
        xml_rec = self.env.ref("mcp_claude.mcp_server_config_default", raise_if_not_found=False)
        if xml_rec and xml_rec.openai_model:
            return xml_rec.openai_model
        config = self.sudo().search([], limit=1)
        return config.openai_model if config and config.openai_model else "gpt-4o"

    def action_test_claude_connection(self):
        """Server-side lightweight API verification test for Anthropic Claude."""
        self.ensure_one()
        api_key = self.get_claude_api_key()
        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Claude Connection Failed',
                    'message': 'No API key configured. Please enter your Anthropic API key in the configuration field above and click Save.',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}]
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            if resp.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Claude Connection Successful',
                        'message': 'Successfully verified server-side connection to Anthropic Claude 3.5 Sonnet API!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                err_msg = ""
                try:
                    err_data = resp.json()
                    if isinstance(err_data, dict) and "error" in err_data:
                        err_msg = err_data["error"].get("message", "")
                except Exception:
                    err_msg = resp.text[:200]

                detail = f": {err_msg}" if err_msg else ""
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Claude Connection Failed',
                        'message': f'Anthropic API Error ({resp.status_code}){detail}',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Claude Connection Failed',
                    'message': f'Network communication error: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_test_openai_connection(self):
        """Server-side lightweight API verification test for OpenAI."""
        self.ensure_one()
        api_key = self.get_openai_api_key()
        model_name = self.get_openai_model()

        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'OpenAI Connection Failed',
                    'message': 'No OpenAI API key configured. Please enter your OpenAI API key in the configuration field above and click Save.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": model_name or "gpt-4o",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Reply with exactly: OPENAI_TEST_OK"}]
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                content = ""
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'OpenAI Connection Successful',
                        'message': f'Successfully verified server-side connection to OpenAI API ({model_name})! Response: {content}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                err_msg = ""
                try:
                    err_data = resp.json()
                    if isinstance(err_data, dict) and "error" in err_data:
                        err_msg = err_data["error"].get("message", "")
                except Exception:
                    err_msg = resp.text[:200]

                detail = f": {err_msg}" if err_msg else ""
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'OpenAI Connection Failed',
                        'message': f'OpenAI API Error ({resp.status_code}){detail}',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'OpenAI Connection Failed',
                    'message': f'Network communication error: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    @api.model
    def get_twilio_caller_number(self):
        """Retrieve Twilio Caller ID from configuration or fall back to canonical twilio.service."""
        xml_rec = self.env.ref("mcp_claude.mcp_server_config_default", raise_if_not_found=False)
        if xml_rec and xml_rec.twilio_caller_number:
            return xml_rec.twilio_caller_number

        config = self.sudo().search([], limit=1)
        if config and config.twilio_caller_number:
            return config.twilio_caller_number

        # Fallback to canonical Twilio module service
        if "twilio.service" in self.env:
            try:
                phone = self.env["twilio.service"].get_twilio_phone_number()
                if phone:
                    return phone
            except Exception:
                pass

        return self.env['ir.config_parameter'].sudo().get_param('twilio_dialer.phone_number', '')

    def action_test_twilio_connection(self):
        """Server-side verification test for Twilio Dialer integration."""
        self.ensure_one()
        caller_num = self.get_twilio_caller_number()
        
        if "twilio.service" not in self.env:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Twilio Connection Warning',
                    'message': 'Twilio Dialer module (twilio_dialer) is not installed in this database.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            twilio_svc = self.env["twilio.service"]
            phone_num = twilio_svc.get_twilio_phone_number()
            if not phone_num and not caller_num:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Twilio Connection Warning',
                        'message': 'No caller number configured. Please enter a caller number or configure twilio_dialer in Settings.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Twilio Connection Successful',
                    'message': f'Twilio Power Dialer service active. Caller ID Number: {caller_num or phone_num}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Twilio Connection Verification Failed',
                    'message': f'Twilio Service Error: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    @api.model
    def get_config_data(self):
        """Returns sanitized server configuration object for UI frontend."""
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({'name': 'Default MCP Settings'})
        
        c_key = config.claude_api_key or ""
        o_key = config.openai_api_key or ""

        return {
            'id': config.id,
            'ai_provider': config.ai_provider or 'claude',
            'claude_api_key_masked': ("••••••••" + c_key[-4:]) if len(c_key) >= 4 else ("••••••••" if c_key else ""),
            'has_claude_key': bool(c_key),
            'claude_model': 'claude-3-5-sonnet-20241022',
            'openai_api_key_masked': ("••••••••" + o_key[-4:]) if len(o_key) >= 4 else ("••••••••" if o_key else ""),
            'has_openai_key': bool(o_key),
            'openai_model': config.openai_model or 'gpt-4o',
            'enable_twilio_dialer': bool(config.enable_twilio_dialer),
            'twilio_caller_number': config.twilio_caller_number or '',
        }

    @api.model
    def save_config_data(self, vals):
        """Saves configuration updates cleanly from frontend UI."""
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({'name': 'Default MCP Settings'})

        update_vals = {}
        if 'ai_provider' in vals:
            update_vals['ai_provider'] = vals['ai_provider']
        if 'openai_model' in vals:
            update_vals['openai_model'] = vals['openai_model']
        if 'enable_twilio_dialer' in vals:
            update_vals['enable_twilio_dialer'] = bool(vals['enable_twilio_dialer'])
        if 'twilio_caller_number' in vals:
            update_vals['twilio_caller_number'] = (vals['twilio_caller_number'] or "").strip()

        # Update API keys if non-masked new value provided
        if vals.get('claude_api_key') and not vals['claude_api_key'].startswith('••••'):
            update_vals['claude_api_key'] = vals['claude_api_key'].strip()
        if vals.get('openai_api_key') and not vals['openai_api_key'].startswith('••••'):
            update_vals['openai_api_key'] = vals['openai_api_key'].strip()

        config.sudo().write(update_vals)
        return {'success': True, 'config': self.get_config_data()}

    @api.model
    def test_provider_connection(self, provider_type):
        """Triggers manual connection verification test for specified provider ('claude', 'openai', 'twilio')."""
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({'name': 'Default MCP Settings'})

        if provider_type == 'claude':
            res = config.action_test_claude_connection()
        elif provider_type == 'openai':
            res = config.action_test_openai_connection()
        elif provider_type == 'twilio':
            res = config.action_test_twilio_connection()
        else:
            return {'success': False, 'error': f'Unknown provider type {provider_type}'}

        params = res.get('params', {}) if isinstance(res, dict) else {}
        return {
            'success': params.get('type') == 'success',
            'title': params.get('title', 'Connection Test'),
            'message': params.get('message', ''),
            'type': params.get('type', 'info')
        }

