import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

shell_script = """
partners = env['res.partner'].search([('phone', '!=', False)], limit=5)
print("PROD_FOUND_PARTNERS=" + str(len(partners)))

dialer = env['twilio.auto.dialer'].create({
    'name': 'Production Odoo Shell Verification Campaign',
    'user_id': 2,
    'partner_ids': [(6, 0, partners.ids)]
})

print("PROD_DIALER_ID=" + str(dialer.id))
print("PROD_PARTNER_IDS_COUNT=" + str(len(dialer.partner_ids)))
print("PROD_QUEUE_LINE_IDS_COUNT=" + str(len(dialer.queue_line_ids)))

dialer.write({'partner_ids': [(6, 0, partners.ids)]})
print("PROD_QUEUE_LINES_AFTER_DUPLICATE_WRITE=" + str(len(dialer.queue_line_ids)))

env.cr.rollback()
print("PROD_VERIFICATION_SUCCESSFUL=True")
"""

# Copy script to remote server
subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\mcp_claude\\tests\\verify_prod_dialer.py {target}:/tmp/verify_script.py', shell=True, check=True)

# Run via native odoo-bin shell
cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin shell -c /etc/odoo/odoo.conf -d odoo18 --no-http < /tmp/verify_script.py"
res = subprocess.run(['ssh', '-i', ssh_key, '-o', 'StrictHostKeyChecking=accept-new', target, cmd], capture_output=True, text=True)

print("=== REMOTE ODOO SHELL FULL OUTPUT ===")
print(res.stdout)
if res.stderr:
    print("[STDERR]\n", res.stderr[-1000:])
