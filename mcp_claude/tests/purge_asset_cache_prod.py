import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("=== PURGING ASSET BUNDLE CACHE & UPGRADING TO 18.0.1.0.4 ===")

# 1. Sync files
tar_cmd = f'tar -C D:\\odoo-mcp -cf - mcp_claude | ssh -i "{ssh_key}" -o StrictHostKeyChecking=accept-new {target} "sudo tar -xf - -C /opt/odoo/custom-addons && sudo chown -R odoo:odoo /opt/odoo/custom-addons"'
subprocess.run(tar_cmd, shell=True)

# 2. Script to delete ir.attachment asset bundles in PostgreSQL
purge_script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
cr = odoo.registry('odoo18_db').cursor()
env = odoo.api.Environment(cr, 1, {})
attachments = env['ir.attachment'].search([('url', 'like', '%assets%')])
print(f'Deleting {len(attachments)} cached asset attachment records...')
attachments.unlink()
cr.commit()
cr.close()
print('CACHED ASSET BUNDLES PURGED SUCCESSFULLY!')
"""

with open("D:\\odoo-mcp\\purge_assets.py", "w") as f:
    f.write(purge_script)

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\purge_assets.py {target}:/tmp/purge_assets.py', shell=True)

# 3. Stop odoo18, purge attachments, upgrade module, start odoo18
cmd = """
sudo systemctl stop odoo18
sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/purge_assets.py
sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init
sudo systemctl start odoo18
sudo systemctl is-active odoo18
"""

res = subprocess.run(['ssh', '-i', ssh_key, target, cmd], capture_output=True, text=True)
print("=== RESULT ===")
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr[-500:])
