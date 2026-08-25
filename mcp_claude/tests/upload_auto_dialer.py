import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

# SCP local auto_dialer.py to remote /tmp
subprocess.run(f'scp -i "{ssh_key}" D:\\Odoo\\custom_addons\\twilio_dialer\\models\\auto_dialer.py {target}:/tmp/auto_dialer.py', shell=True, check=True)

# Copy to custom-addons, upgrade twilio_dialer, and restart service
cmd = """
sudo cp /tmp/auto_dialer.py /opt/odoo/custom-addons/twilio_dialer/models/auto_dialer.py
sudo chown odoo:odoo /opt/odoo/custom-addons/twilio_dialer/models/auto_dialer.py
sudo systemctl stop odoo18
sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18 -u twilio_dialer --stop-after-init
sudo systemctl start odoo18
sudo systemctl is-active odoo18
"""

res = subprocess.run(['ssh', '-i', ssh_key, '-o', 'StrictHostKeyChecking=accept-new', target, cmd], capture_output=True, text=True)

print("=== REMOTE UPLOAD AND UPGRADE RESULTS ===")
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr[-500:])
