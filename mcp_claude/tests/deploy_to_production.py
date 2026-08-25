import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

files_to_sync = [
    r"mcp_claude\models\mcp_ai_conversation.py",
    r"mcp_claude\models\mcp_ai_conversation_service.py",
    r"mcp_claude\controllers\ai_chat_controller.py",
    r"mcp_claude\static\src\js\ai_chat_service.js",
    r"mcp_claude\static\src\js\components\ai_chat_window.js",
    r"mcp_claude\static\src\xml\ai_bubble_container.xml",
    r"mcp_claude\static\src\xml\ai_chat_window.xml",
    r"mcp_claude\__manifest__.py",
]

print("=== 1. UPLOADING UPDATED FILES TO PRODUCTION SERVER ===")
for rel_path in files_to_sync:
    local_p = rf"D:\odoo-mcp\{rel_path}"
    remote_p = f"/opt/odoo/custom-addons/{rel_path.replace('\\', '/')}"
    print(f"Uploading {rel_path} -> {remote_p}")
    subprocess.run(f'scp -i "{ssh_key}" "{local_p}" {target}:"{remote_p}"', shell=True, check=True)

print("\n=== 2. UPGRADING MODULE mcp_claude ON PRODUCTION DATABASE odoo18_db ===")
upgrade_cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init"
res = subprocess.run(['ssh', '-i', ssh_key, target, upgrade_cmd], capture_output=True, text=True)
print("UPGRADE LOG OUTPUT:")
print(res.stdout[-1500:])
if res.stderr:
    print("[STDERR]", res.stderr[-1000:])

print("\n=== 3. RESTARTING ODOO18 SYSTEMD SERVICE ON PRODUCTION SERVER ===")
subprocess.run(['ssh', '-i', ssh_key, target, 'sudo systemctl restart odoo18'], check=True)
print("Odoo18 Service restarted successfully!")
