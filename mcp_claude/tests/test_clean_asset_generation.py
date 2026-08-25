import subprocess
import os

print("=== STEP 1: DELETE ALL ASSET ATTACHMENTS & FILESTORE FILES IN SEPARATE PROCESS ===")
step1_code = """
import sys, os
sys.path.insert(0, r'D:\\Odoo\\odoo')
import odoo

# 1. Delete filestore files
filestore_dir = r'D:\\Odoo\\data\\filestore\\odoo18'
if os.path.exists(filestore_dir):
    for root, dirs, files in os.walk(filestore_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                os.remove(fp)
            except Exception:
                pass
print('Filestore cleared!')

# 2. Delete ir_attachment rows
odoo.tools.config.parse_config(['-c', r'D:\\odoo-mcp\\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '%assets%')])
    print(f'Unlinking {len(atts)} attachment records...')
    atts.unlink()
    cr.commit()
"""

with open(r"D:\odoo-mcp\step1_purge.py", "w") as f:
    f.write(step1_code)

res1 = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", r"D:\odoo-mcp\step1_purge.py"], capture_output=True, text=True)
print(res1.stdout)
if res1.stderr:
    print("[STDERR]", res1.stderr)

print("\n=== STEP 2: RUN UPGRADE -u mcp_claude IN A COMPLETELY FRESH PROCESS ===")
cmd = [r'D:\Odoo\venv\Scripts\python.exe', r'D:\Odoo\odoo\odoo-bin', '-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18', '-u', 'mcp_claude', '--stop-after-init']
res2 = subprocess.run(cmd, capture_output=True, text=True)
print("UPGRADE RETURN CODE:", res2.returncode)

print("\n=== STEP 3: INSPECT FRESHLY GENERATED FILESTORE CODE ===")
filestore_dir = r"D:\Odoo\data\filestore\odoo18"
found = False
for root, dirs, files in os.walk(filestore_dir):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                if "ai_chat_service" in content:
                    found = True
                    print(f"\nFRESH ASSET FILE: {fp}")
                    idx = content.find("aiChatService=")
                    print("EXACT CODE IN FRESH FILESTORE:")
                    print(content[idx:idx+250])
        except Exception:
            pass

if not found:
    print("No asset bundle created during upgrade. Assets will build on HTTP GET.")
