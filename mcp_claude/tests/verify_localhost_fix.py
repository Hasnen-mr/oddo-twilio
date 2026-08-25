import urllib.request
import json
import http.cookiejar
import subprocess

print("==========================================================")
print("PURGING LOCALHOST ASSET ATTACHMENTS & TESTING DEPLOYMENT")
print("==========================================================")

# 1. Unlink local asset attachments
purge_script = """
import sys
sys.path.insert(0, r"D:\\Odoo")
import odoo
odoo.tools.config.parse_config(['-c', r'D:\\odoo-mcp\\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '/web/assets/%')])
    print('Unlinked', len(atts), 'attachment records on localhost...')
    atts.unlink()
    cr.commit()
"""
res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", purge_script], capture_output=True, text=True)
print("Purge stdout:", res.stdout)
print("Purge stderr:", res.stderr)

# 2. Authenticate & fetch bundle
url = "http://localhost:8069"
db = "odoo18"
user = "admin"
pwd = "zantatech@odoo"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

op.open(urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':db,'login':user,'password':pwd}}).encode(), headers={'Content-Type':'application/json'}))

html = op.open(f"{url}/web").read().decode('utf-8')
urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]
asset_url = [u for u in urls if 'web.assets_web' in u or 'web.assets_backend' in u][0]

js = op.open(f"{url}{asset_url}").read().decode('utf-8', errors='ignore')

print("\n=== LOCALHOST BUNDLE VERIFICATION ===")
print("Bundle URL:", asset_url)
print("Bundle Length:", len(js), "bytes")
print("AIBubbleContainer:", 'AIBubbleContainer' in js)
print("AIChatWindow:", 'AIChatWindow' in js)
print("AIChatSkeleton:", 'AIChatSkeleton' in js)
print("AIBubbleTrigger:", 'AIBubbleTrigger' in js)
