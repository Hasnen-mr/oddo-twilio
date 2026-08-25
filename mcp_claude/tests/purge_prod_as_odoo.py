import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
host = "dev.gulani@34.55.237.237"

cmd = """
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

ssh_command = ["ssh", "-i", ssh_key, host, cmd]
res = subprocess.run(ssh_command, capture_output=True, text=True)
print("=== ASSET CACHE PURGE RESULT ===")
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
print("STDERR:\n", res.stderr)
