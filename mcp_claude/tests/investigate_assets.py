import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("==========================================================")
print("1. LOCAL DISK FILE CONTENT CHECK")
print("==========================================================")
with open(r"D:\odoo-mcp\mcp_claude\static\src\js\ai_chat_service.js", "r", encoding="utf-8") as f:
    print(f.read()[:500])

print("\n==========================================================")
print("2. REMOTE PRODUCTION SERVER DISK FILE CONTENT CHECK")
print("==========================================================")
cat_cmd = 'cat /opt/odoo/custom-addons/mcp_claude/static/src/js/ai_chat_service.js'
res = subprocess.run(['ssh', '-i', ssh_key, target, cat_cmd], capture_output=True, text=True)
print(res.stdout[:500])

print("\n==========================================================")
print("3. REMOTE PRODUCTION DATABASE IR.ATTACHMENT ASSETS CHECK")
print("==========================================================")
db_inspect_script = """
import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18_db'])
cr = odoo.registry('odoo18_db').cursor()
env = odoo.api.Environment(cr, 1, {})

attachments = env['ir.attachment'].search([('url', 'like', '%assets%')])
print(f'Total asset attachment records found: {len(attachments)}')

found_service_in_db = False
for att in attachments:
    raw_data = att.raw or b''
    if b'ai_chat_service' in raw_data:
        found_service_in_db = True
        print(f'\\n[ATTACHMENT ID {att.id}] Name: {att.name} | URL: {att.url} | Checksum: {att.checksum} | Date: {att.create_date}')
        # Find lines containing ai_chat_service or dependencies
        text = raw_data.decode('utf-8', errors='ignore')
        for line in text.split(';'):
            if 'ai_chat_service' in line:
                print('   BUNDLED JS SNIPPET:', line[:300])

if not found_service_in_db:
    print('NO asset attachment in DB contains ai_chat_service!')

cr.close()
"""

with open(r"D:\odoo-mcp\db_inspect.py", "w") as f:
    f.write(db_inspect_script)

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\db_inspect.py {target}:/tmp/db_inspect.py', shell=True)
run_cmd = 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/db_inspect.py'
res2 = subprocess.run(['ssh', '-i', ssh_key, target, run_cmd], capture_output=True, text=True)
print(res2.stdout)
if res2.stderr:
    print("[STDERR]", res2.stderr[-500:])
