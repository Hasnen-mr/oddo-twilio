import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
cr = odoo.registry('odoo18_db').cursor()
env = odoo.api.Environment(cr, 1, {})
env['res.users'].search([('login', '=', 'admin')], limit=1).write({'password': 'admin'})
cr.commit()
cr.close()
print('PROD ADMIN PASSWORD SET TO admin ON odoo18_db!')
"""

with open("D:\\odoo-mcp\\reset_prod.py", "w") as f:
    f.write(script)

# Upload script
subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\reset_prod.py {target}:/tmp/reset_prod.py', shell=True)

# Upgrade module on odoo18_db
cmd = """
sudo systemctl stop odoo18
sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init
sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/reset_prod.py
sudo systemctl start odoo18
"""
res = subprocess.run(['ssh', '-i', ssh_key, target, cmd], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr)
