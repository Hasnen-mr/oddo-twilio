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

print("==========================================================")
print("PURGING PRODUCTION ASSET CACHE & REBUILDING BUNDLE")
print("==========================================================")

# 1. Unlink ir.attachment assets on odoo18_db
purge_script = """
sudo /opt/odoo/venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
with odoo.registry('odoo18_db').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '/web/assets/%')])
    print('Unlinking', len(atts), 'attachment records from production...')
    atts.unlink()
    cr.commit()
"
"""
run_ssh(purge_script, "1. UNLINKING PRODUCTION ASSET ATTACHMENTS")

# 2. Upgrade mcp_claude module on production odoo18_db
run_ssh("sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo18/odoo-bin -c /etc/odoo/odoo.conf -d odoo18_db -u mcp_claude --stop-after-init", "2. UPGRADING MODULE mcp_claude ON PRODUCTION DATABASE")

# 3. Restart Odoo service
run_ssh("sudo systemctl restart odoo18", "3. RESTARTING ODOO SERVICE")
