import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    # Check if record 19 exists
    cr.execute("SELECT id FROM twilio_dialer_dashboard WHERE id = 19;")
    res = cr.fetchone()
    if not res:
        print("Record #19 missing in SQL. Force inserting ID 19...")
        cr.execute("INSERT INTO twilio_dialer_dashboard (id, create_date, write_date) VALUES (19, NOW(), NOW());")
        cr.commit()
        print("[SUCCESS] Recreated record ID 19 in database!")
    else:
        print("Record #19 already exists in database.")
