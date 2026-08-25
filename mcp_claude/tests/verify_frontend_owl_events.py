import subprocess
import json
import time

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("==========================================================================")
print("FRONTEND OWL COMPONENT RUNTIME EVENT TRACE & LIFECYCLE AUDIT")
print("==========================================================================")

# 1. Fetch live JS bundle from production server to verify OWL component event setup
cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 -c \"import urllib.request, json, http.cookiejar; cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18_db','login':'admin','password':'admin'}}).encode(), headers={'Content-Type':'application/json'})); html = op.open('http://localhost:8069/web').read().decode('utf-8'); urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]; print([u for u in urls if 'web.assets_web' in u])\""

res = subprocess.run(['ssh', '-i', ssh_key, target, cmd], capture_output=True, text=True)
print("PRODUCTION BUNDLE LOADED:", res.stdout.strip())

# 2. Inspect exact compiled OWL event listeners in production bundle
inspect_cmd = "sudo -u odoo /opt/odoo/venv/bin/python3 -c \"import urllib.request, json, http.cookiejar; cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18_db','login':'admin','password':'admin'}}).encode(), headers={'Content-Type':'application/json'})); js = op.open('http://localhost:8069/web/assets/787e197/web.assets_web.min.js').read().decode('utf-8', errors='ignore'); idx = js.find('ACTION_MANAGER:UPDATE'); print('EXACT BUNDLE CODE NEAR LISTENERS:'); print(js[idx-100:idx+350])\""

res2 = subprocess.run(['ssh', '-i', ssh_key, target, inspect_cmd], capture_output=True, text=True)
print(res2.stdout)
