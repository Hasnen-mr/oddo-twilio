import urllib.request
import json
import http.cookiejar

url = "https://odoo.zantatech.com"
db = "odoo18_db"
user = "admin"
pwd = "zantatech@odoo"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Authenticate
op.open(urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':db,'login':user,'password':pwd}}).encode(), headers={'Content-Type':'application/json'}))

# Fetch web HTML
html = op.open(f"{url}/web").read().decode('utf-8')
urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]
asset_url = [u for u in urls if 'web.assets_web' in u or 'web.assets_backend' in u][0]

js = op.open(f"{url}{asset_url}").read().decode('utf-8', errors='ignore')

print("=== PRODUCTION BUNDLE VERIFICATION ===")
print("Bundle URL:", asset_url)
print("Bundle Length:", len(js), "bytes")
print("AIBubbleContainer:", 'AIBubbleContainer' in js)
print("AIChatWindow:", 'AIChatWindow' in js)
print("AIChatSkeleton:", 'AIChatSkeleton' in js)
print("AIBubbleTrigger:", 'AIBubbleTrigger' in js)
