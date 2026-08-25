import sys
import subprocess
import json
import http.cookiejar

# 1. Update password on Local Server database 'odoo18'
sys.path.insert(0, r'D:\Odoo\odoo')
import odoo
odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])

print("==========================================================")
print("1. UPDATING ADMIN PASSWORD ON LOCAL DATABASE (odoo18)")
print("==========================================================")
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)
    if admin_user:
        admin_user.write({'password': 'zantatech@odoo'})
        cr.commit()
        print(f"[PASS] Local admin password successfully updated to 'zantatech@odoo' for user ID {admin_user.id}")

# 2. Update password on Remote Production Server database 'odoo18_db'
print("\n==========================================================")
print("2. UPDATING ADMIN PASSWORD ON PRODUCTION DATABASE (odoo18_db)")
print("==========================================================")

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

prod_update_script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
cr = odoo.registry('odoo18_db').cursor()
env = odoo.api.Environment(cr, 1, {})
admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)
if admin_user:
    admin_user.write({'password': 'zantatech@odoo'})
    cr.commit()
    print(f"[PASS] Production admin password successfully updated to 'zantatech@odoo' for user ID {admin_user.id}")
cr.close()
"""

with open(r"D:\odoo-mcp\update_prod_pwd_tmp.py", "w") as f:
    f.write(prod_update_script)

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\update_prod_pwd_tmp.py {target}:/tmp/update_prod_pwd.py', shell=True, check=True)
res = subprocess.run(['ssh', '-i', ssh_key, target, 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/update_prod_pwd.py'], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("[STDERR]", res.stderr)

print("\n==========================================================")
print("3. VERIFYING LOGIN WITH NEW PASSWORD 'zantatech@odoo'")
print("==========================================================")

def test_login(url, db, user, pwd, label):
    try:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        payload = {'jsonrpc': '2.0', 'id': 1, 'params': {'db': db, 'login': user, 'password': pwd}}
        req = urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        res = json.loads(op.open(req).read().decode())
        if 'result' in res and res['result'].get('uid'):
            print(f"[VERIFIED] {label}: Login SUCCESSFUL with password 'zantatech@odoo' (UID: {res['result']['uid']})")
        else:
            print(f"[FAIL] {label}: Login failed. Response: {res}")
    except Exception as e:
        print(f"[ERROR] {label}: {e}")

test_login('http://localhost:8069', 'odoo18', 'admin', 'zantatech@odoo', 'Local Odoo Server')
test_login('http://34.55.237.237:8069', 'odoo18_db', 'admin', 'zantatech@odoo', 'Production Odoo Server')
