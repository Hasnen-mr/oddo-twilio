import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
print('PROD DATABASES:', odoo.service.db.list_dbs())
"""

with open("D:\\odoo-mcp\\check_dbs.py", "w") as f:
    f.write(script)

up_cmd = f'scp -i "{ssh_key}" D:\\odoo-mcp\\check_dbs.py {target}:/tmp/check_dbs.py'
subprocess.run(up_cmd, shell=True)

run_cmd = 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/check_dbs.py'
res = subprocess.run(['ssh', '-i', ssh_key, target, run_cmd], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr)
