import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("=== RESETTING ADMIN PASSWORD & VERIFYING PROD ===")

reset_script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18'])
cr = odoo.registry('odoo18').cursor()
env = odoo.api.Environment(cr, 1, {})
env['res.users'].search([('login', '=', 'admin')], limit=1).write({'password': 'admin'})
cr.commit()
cr.close()
print('PROD ADMIN PASSWORD SET TO admin!')
"""

with open("D:\\odoo-mcp\\reset_pass.py", "w") as f:
    f.write(reset_script)

# Upload script
up_cmd = f'scp -i "{ssh_key}" D:\\odoo-mcp\\reset_pass.py {target}:/tmp/reset_pass.py'
subprocess.run(up_cmd, shell=True)

# Run script
run_cmd = 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/reset_pass.py'
res = subprocess.run(['ssh', '-i', ssh_key, target, run_cmd], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr)
