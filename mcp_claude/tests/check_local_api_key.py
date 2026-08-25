import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    config = env["mcp.server.config"].sudo().search([], limit=1)
    key_in_config = getattr(config, "claude_api_key", None) if config else None
    key_in_param = env['ir.config_parameter'].sudo().get_param('mcp_claude.claude_api_key', None)
    
    print("==========================================================")
    print("INSPECTING LOCAL CLAUDE API KEY CONFIGURATION")
    print("==========================================================")
    print("Key in mcp.server.config:", key_in_config[:10] + "..." if key_in_config else "None")
    print("Key in ir.config_parameter:", key_in_param[:10] + "..." if key_in_param else "None")
