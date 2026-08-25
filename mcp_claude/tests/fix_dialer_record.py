import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    if 'twilio.dialer.dashboard' in env:
        records = env['twilio.dialer.dashboard'].search([])
        print("Active twilio.dialer.dashboard records:", [(r.id, r.name if hasattr(r, 'name') else r.display_name) for r in records])
        if not records:
            new_rec = env['twilio.dialer.dashboard'].create({})
            print(f"Created fresh twilio.dialer.dashboard record #{new_rec.id}")
