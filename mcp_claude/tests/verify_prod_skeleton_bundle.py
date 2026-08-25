import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

cmd = """sudo -u odoo /opt/odoo/venv/bin/python3 -c "
import urllib.request, json, http.cookiejar
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18_db','login':'admin','password':'zantatech@odoo'}}).encode(), headers={'Content-Type':'application/json'}))
html = op.open('http://localhost:8069/web').read().decode('utf-8')
urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]
asset_url = [u for u in urls if 'web.assets_backend' in u or 'web.assets_web' in u][0]
js = op.open('http://localhost:8069' + asset_url).read().decode('utf-8', errors='ignore')
print('BUNDLE URL:', asset_url)
print('AIChatSkeleton IN BUNDLE:', 'AIChatSkeleton' in js)
print('AbortController IN BUNDLE:', 'activeAbortController' in js)
print('draftPrompts IN BUNDLE:', 'draftPrompts' in js)
"
"""

res = subprocess.run(['ssh', '-i', ssh_key, target, cmd], capture_output=True, text=True)
print(res.stdout)
