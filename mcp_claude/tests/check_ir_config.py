import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    params = env['ir.config_parameter'].sudo().search([('key', 'like', 'mcp')])
    print("MCP ir.config_parameter records:")
    for p in params:
        print(f"  {p.key} = {p.value}")
