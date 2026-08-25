import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
host = "dev.gulani@34.55.237.237"

def run_ssh(cmd, label):
    print(f"=== {label} ===")
    ssh_command = ["ssh", "-i", ssh_key, host, cmd]
    res = subprocess.run(ssh_command, capture_output=True, text=True)
    print(f"Exit Code: {res.returncode}")
    if res.stdout:
        print("STDOUT:\n" + res.stdout)
    if res.stderr:
        print("STDERR:\n" + res.stderr)
    return res.returncode == 0

def scp_file(local_path, remote_path):
    print(f"Uploading {local_path} -> {remote_path}")
    cmd = ["scp", "-i", ssh_key, local_path, f"{host}:{remote_path}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0

print("==========================================================")
print("UPLOADING PHASE 2 BACKEND & UI COMPONENTS TO PRODUCTION (NO COMMIT)")
print("==========================================================")

# 1. Upload files
scp_file(r"D:\odoo-mcp\mcp_claude\models\mcp_ai_prompt_builder.py", "/tmp/mcp_ai_prompt_builder.py")
scp_file(r"D:\odoo-mcp\mcp_claude\models\providers\mcp_ai_provider_claude.py", "/tmp/mcp_ai_provider_claude.py")
scp_file(r"D:\odoo-mcp\mcp_claude\models\mcp_ai_conversation_service.py", "/tmp/mcp_ai_conversation_service.py")
scp_file(r"D:\odoo-mcp\mcp_claude\controllers\ai_chat_controller.py", "/tmp/ai_chat_controller.py")
scp_file(r"D:\odoo-mcp\mcp_claude\static\src\js\components\ai_bubble_trigger.js", "/tmp/ai_bubble_trigger.js")
scp_file(r"D:\odoo-mcp\mcp_claude\static\src\js\components\ai_bubble_container.js", "/tmp/ai_bubble_container.js")
scp_file(r"D:\odoo-mcp\mcp_claude\static\src\xml\ai_bubble_container.xml", "/tmp/ai_bubble_container.xml")
scp_file(r"D:\odoo-mcp\mcp_claude\static\src\scss\ai_bubble.scss", "/tmp/ai_bubble.scss")

# Move from /tmp/ to addon directory
move_cmd = """
sudo mv /tmp/mcp_ai_prompt_builder.py /opt/odoo/custom-addons/mcp_claude/models/mcp_ai_prompt_builder.py
sudo mv /tmp/mcp_ai_provider_claude.py /opt/odoo/custom-addons/mcp_claude/models/providers/mcp_ai_provider_claude.py
sudo mv /tmp/mcp_ai_conversation_service.py /opt/odoo/custom-addons/mcp_claude/models/mcp_ai_conversation_service.py
sudo mv /tmp/ai_chat_controller.py /opt/odoo/custom-addons/mcp_claude/controllers/ai_chat_controller.py
sudo mv /tmp/ai_bubble_trigger.js /opt/odoo/custom-addons/mcp_claude/static/src/js/components/ai_bubble_trigger.js
sudo mv /tmp/ai_bubble_container.js /opt/odoo/custom-addons/mcp_claude/static/src/js/components/ai_bubble_container.js
sudo mv /tmp/ai_bubble_container.xml /opt/odoo/custom-addons/mcp_claude/static/src/xml/ai_bubble_container.xml
sudo mv /tmp/ai_bubble.scss /opt/odoo/custom-addons/mcp_claude/static/src/scss/ai_bubble.scss
sudo chown -R odoo:odoo /opt/odoo/custom-addons/mcp_claude
"""
run_ssh(move_cmd, "1. MOVING FILES TO CUSTOM-ADDONS")

# 2. Unlink stale asset attachments
purge_script = """
sudo -u odoo /opt/odoo/venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
with odoo.registry('odoo18_db').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '/web/assets/%')])
    print('Unlinked', len(atts), 'attachment records from production...')
    atts.unlink()
    cr.commit()
"
"""
run_ssh(purge_script, "2. UNLINKING ASSET CACHE ATTACHMENTS")

# 3. Upgrade mcp_claude module
run_ssh("sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init", "3. UPGRADING mcp_claude MODULE")

# 4. Restart Odoo service
run_ssh("sudo systemctl restart odoo18", "4. RESTARTING ODOO SERVICE")
