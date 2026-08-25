import sys
sys.path.insert(0, r'D:\Odoo\odoo')
import odoo

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])

print("==========================================================")
print("PURGING LOCAL ASSET CACHE ATTACHMENTS FOR DATABASE odoo18")
print("==========================================================")

with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '/web/assets/%')])
    count = len(atts)
    atts.unlink()
    cr.commit()
    print(f"[PASS] Unlinked {count} stale local web asset attachment records from database 'odoo18'")

print("\n==========================================================")
print("UPGRADING MODULE mcp_claude ON LOCAL DATABASE odoo18")
print("==========================================================")
