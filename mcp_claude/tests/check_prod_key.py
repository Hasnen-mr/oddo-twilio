import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
with odoo.registry('odoo18_db').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    k = env['ir.config_parameter'].sudo().get_param('mcp_claude.claude_api_key', None)
    print("PROD_KEY_PRESENT:", bool(k and k != "mcp_live_default"))
    if k:
        print("PROD_KEY_PREFIX:", k[:12] + "...")
