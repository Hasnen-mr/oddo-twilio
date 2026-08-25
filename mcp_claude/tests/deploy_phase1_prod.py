import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("=== DEPLOYING PHASE 1 AI BUBBLE TO REMOTE PRODUCTION SERVER ===")

# Sync mcp_claude files to remote server
tar_cmd = f'tar -C D:\\odoo-mcp -cf - mcp_claude | ssh -i "{ssh_key}" -o StrictHostKeyChecking=accept-new {target} "sudo tar -xf - -C /opt/odoo/custom-addons && sudo chown -R odoo:odoo /opt/odoo/custom-addons"'
res0 = subprocess.run(tar_cmd, shell=True, capture_output=True, text=True)
print("TAR UPLOAD STATUS:", res0.returncode)

# Upgrade module and restart service
cmd = """
sudo systemctl stop odoo18
sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18 -u mcp_claude --stop-after-init
sudo systemctl start odoo18
sudo systemctl is-active odoo18
"""

res = subprocess.run(['ssh', '-i', ssh_key, '-o', 'StrictHostKeyChecking=accept-new', target, cmd], capture_output=True, text=True)

print("=== REMOTE UPGRADE RESULTS ===")
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr[-500:])
