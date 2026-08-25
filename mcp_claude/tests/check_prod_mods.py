import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\mcp_claude\\tests\\remote_check_script.py {target}:/tmp/remote_check_script.py', shell=True, check=True)

cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin shell -c /etc/odoo/odoo.conf -d odoo18 --no-http < /tmp/remote_check_script.py"
res = subprocess.run(['ssh', '-i', ssh_key, '-o', 'StrictHostKeyChecking=accept-new', target, cmd], capture_output=True, text=True)

print("=== REMOTE MODULE STATUS ===")
print(res.stdout)
