import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    
    print("mcp.api.key fields:", list(env['mcp.api.key']._fields.keys()))
    print("mcp.server.config fields:", list(env['mcp.server.config']._fields.keys()))
