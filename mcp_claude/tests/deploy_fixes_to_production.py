import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

files_to_sync = [
    r"mcp_claude\static\src\js\components\ai_chat_window.js",
    r"mcp_claude\static\src\xml\ai_chat_window.xml",
    r"mcp_claude\static\src\scss\ai_bubble.scss",
    r"mcp_claude\__manifest__.py",
]

print("=== 1. UPLOADING NAVIGATION & BUTTON FIXES TO PRODUCTION SERVER ===")
for rel_path in files_to_sync:
    local_p = rf"D:\odoo-mcp\{rel_path}"
    remote_p = f"/opt/odoo/custom-addons/{rel_path.replace('\\', '/')}"
    print(f"Uploading {rel_path} -> {remote_p}")
    subprocess.run(f'scp -i "{ssh_key}" "{local_p}" {target}:"{remote_p}"', shell=True, check=True)

print("\n=== 2. UPGRADING MODULE mcp_claude ON PRODUCTION DATABASE odoo18_db ===")
upgrade_cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init"
res = subprocess.run(['ssh', '-i', ssh_key, target, upgrade_cmd], capture_output=True, text=True)
print("UPGRADE LOG OUTPUT:")
print(res.stdout[-1200:])

print("\n=== 3. PURGING PRODUCTION ATTACHMENT ASSET CACHES ===")
purge_script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
cr = odoo.registry('odoo18_db').cursor()
env = odoo.api.Environment(cr, 1, {})

atts = env['ir.attachment'].search([('url', 'like', '%assets%')])
print(f'Unlinking {len(atts)} attachment records from production...')
atts.unlink()
cr.commit()
cr.close()
"""
with open(r"D:\odoo-mcp\purge_prod_assets_tmp2.py", "w") as f:
    f.write(purge_script)

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\purge_prod_assets_tmp2.py {target}:/tmp/purge_prod_assets.py', shell=True)
run_cmd = 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/purge_prod_assets.py'
res2 = subprocess.run(['ssh', '-i', ssh_key, target, run_cmd], capture_output=True, text=True)
print(res2.stdout)

print("\n=== 4. RESTARTING ODOO18 SERVICE ===")
subprocess.run(['ssh', '-i', ssh_key, target, 'sudo systemctl restart odoo18'], check=True)
print("Production Server updated and restarted successfully!")
