import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

cmd = """sudo -u odoo /opt/odoo/venv/bin/python3 -c "
import urllib.request, json, http.cookiejar
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18_db','login':'admin','password':'admin'}}).encode(), headers={'Content-Type':'application/json'}))
js = op.open('http://localhost:8069/web/assets/84ca6f5/web.assets_web.min.js').read().decode('utf-8', errors='ignore')
idx = js.find('AIChatWindow')
print('=== COMPILED OWL COMPONENT IN BUNDLE ===')
print(js[idx-50:idx+650])
"
"""

res = subprocess.run(['ssh', '-i', ssh_key, target, cmd], capture_output=True, text=True)
print(res.stdout)
