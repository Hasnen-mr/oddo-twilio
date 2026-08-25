import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("=== 1. UPLOADING TWILIO DIALER CONTROLLER & JS FIXES TO /tmp/ ===")

files_to_upload = [
    (r"D:\Odoo\custom_addons\twilio_dialer\controllers\twilio_controller.py", "/tmp/twilio_controller.py", "/opt/odoo/custom-addons/twilio_dialer/controllers/twilio_controller.py"),
    (r"D:\Odoo\custom_addons\twilio_dialer\static\src\js\device_manager.js", "/tmp/device_manager.js", "/opt/odoo/custom-addons/twilio_dialer/static/src/js/device_manager.js"),
]

for local_path, tmp_path, final_path in files_to_upload:
    print(f"Uploading {local_path} -> {tmp_path}")
    subprocess.run(f'scp -i "{ssh_key}" "{local_path}" {target}:{tmp_path}', shell=True, check=True)
    subprocess.run(['ssh', '-i', ssh_key, target, f'sudo cp {tmp_path} {final_path} && sudo chown odoo:odoo {final_path}'], check=True)

print("\n=== 2. UPGRADING MODULE twilio_dialer ON PRODUCTION DATABASE odoo18_db ===")
upgrade_cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u twilio_dialer --stop-after-init"
res = subprocess.run(['ssh', '-i', ssh_key, target, upgrade_cmd], capture_output=True, text=True)
print("UPGRADE LOG OUTPUT:")
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr[-500:])

print("\n=== 3. PURGING PRODUCTION ATTACHMENT ASSET CACHES ===")
purge_cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 -c \"import sys; sys.path.insert(0, '/opt/odoo/odoo18'); import odoo; odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db']); cr = odoo.registry('odoo18_db').cursor(); env = odoo.api.Environment(cr, 1, {}); atts = env['ir.attachment'].search([('url', 'like', '/web/assets/%')]); count = len(atts); atts.unlink(); cr.commit(); print('Unlinked %d attachment records from production...' % count)\""
res_purge = subprocess.run(['ssh', '-i', ssh_key, target, purge_cmd], capture_output=True, text=True)
print(res_purge.stdout.strip())

print("\n=== 4. RESTARTING ODOO18 SERVICE ===")
restart_cmd = "sudo systemctl restart odoo18"
subprocess.run(['ssh', '-i', ssh_key, target, restart_cmd], check=True)
print("Production Server updated and restarted successfully!")
