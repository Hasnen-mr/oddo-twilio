import subprocess
import time
import urllib.request
import json

print("==========================================================================")
print("VERIFYING LOCALHOST HTTP ASSET BUNDLE COMPILATION")
print("==========================================================================")

# 1. Start local Odoo server in background if not running
try:
    urllib.request.urlopen("http://localhost:8069", timeout=2)
    print("[INFO] Local Odoo Server is already running on http://localhost:8069")
except Exception:
    print("[INFO] Starting local Odoo server...")
    proc = subprocess.Popen([r"D:\Odoo\venv\Scripts\python.exe", r"D:\Odoo\odoo\odoo-bin", "-c", r"D:\odoo-mcp\odoo.conf", "-d", "odoo18"], cwd=r"D:\odoo-mcp")
    time.sleep(6)

# 2. Authenticate & inspect localhost asset bundle
cj = urllib.request.HTTPCookieProcessor()
op = urllib.request.build_opener(cj)
op.open(urllib.request.Request("http://localhost:8069/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18','login':'admin','password':'zantatech@odoo'}}).encode(), headers={'Content-Type':'application/json'}))
html = op.open("http://localhost:8069/web").read().decode('utf-8')
urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]
asset_url = [u for u in urls if 'web.assets_web' in u or 'web.assets_backend' in u][0]

js = op.open("http://localhost:8069" + asset_url).read().decode('utf-8', errors='ignore')

print("\n--- LOCALHOST ASSET BUNDLE RESOLUTION RESULT ---")
print("Bundle URL:", asset_url)
print("Length:", len(js), "bytes")
print("Explicit defines in local bundle:")
for m in ["@mcp_claude/js/components/ai_chat_skeleton", "@mcp_claude/js/components/ai_chat_window", "@mcp_claude/js/components/ai_bubble_container"]:
    print(f" - {m}: {'PRESENT IN LOCAL BUNDLE' if m in js else 'MISSING'}")
