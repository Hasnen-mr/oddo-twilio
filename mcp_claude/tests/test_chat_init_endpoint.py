import urllib.request
import json
import http.cookiejar

print("==========================================================")
print("TESTING /mcp/ai/v1/chat/init ENDPOINT ON LOCALHOST")
print("==========================================================")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Authenticate
auth_res = op.open(urllib.request.Request("http://localhost:8069/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':'odoo18','login':'admin','password':'zantatech@odoo'}}).encode(), headers={'Content-Type':'application/json'}))
print("Auth status:", auth_res.status)

# Call /mcp/ai/v1/chat/init
req = urllib.request.Request("http://localhost:8069/mcp/ai/v1/chat/init", data=json.dumps({
    'jsonrpc': '2.0',
    'id': 1,
    'params': {
        'session_id': None,
        'scope': 'global',
        'model_name': None,
        'res_id': None,
        'workspace_app': None
    }
}).encode(), headers={'Content-Type': 'application/json'})

try:
    res = op.open(req)
    data = json.loads(res.read().decode('utf-8'))
    print("Response payload:", json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
