import urllib.request
import json
import http.cookiejar

url = "http://localhost:8069"
db = "odoo18"
user = "admin"
pwd = "zantatech@odoo"

print("==========================================================")
print("TESTING LOCALHOST PHASE 2 TOOL CALLING VIA HTTP JSON-RPC")
print("==========================================================")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

try:
    # 1. Authenticate
    auth_res = op.open(urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':db,'login':user,'password':pwd}}).encode(), headers={'Content-Type':'application/json'}))
    print("1. Authentication Status:", auth_res.status)

    # 2. Init Chat
    init_req = urllib.request.Request(f"{url}/mcp/ai/v1/chat/init", data=json.dumps({
        'jsonrpc': '2.0',
        'id': 1,
        'params': {'scope': 'global'}
    }).encode(), headers={'Content-Type': 'application/json'})

    init_res = op.open(init_req)
    init_data = json.loads(init_res.read().decode('utf-8'))
    conv_id = init_data.get('result', {}).get('conversation_id')
    print("2. Initialized Local Conversation ID:", conv_id)

    # 3. Send Phase 2 Prompt
    msg_req = urllib.request.Request(f"{url}/mcp/ai/v1/chat/message", data=json.dumps({
        'jsonrpc': '2.0',
        'id': 2,
        'params': {
            'conversation_id': conv_id,
            'prompt': 'Show me my open opportunities'
        }
    }).encode(), headers={'Content-Type': 'application/json'})

    msg_res = op.open(msg_req)
    msg_data = json.loads(msg_res.read().decode('utf-8'))
    print("3. Local Response Payload:")
    print(json.dumps(msg_data, indent=2))
except Exception as e:
    print("Localhost error:", e)
