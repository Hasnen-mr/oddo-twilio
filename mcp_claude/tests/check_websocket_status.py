import urllib.request
import json
import http.cookiejar

def test_websocket_health(url, db, user, pwd, label):
    print(f"=== TESTING WEBSOCKET BUS CONNECTION ON {label} ({url}) ===")
    try:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        
        # Authenticate
        auth_res = op.open(urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':db,'login':user,'password':pwd}}).encode(), headers={'Content-Type':'application/json'}))
        
        # Check websocket handhshake endpoint /websocket?version=18.0-7
        ws_req = urllib.request.Request(f"{url}/websocket?version=18.0-7", headers={
            'Upgrade': 'websocket',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
            'Sec-WebSocket-Version': '13'
        })
        try:
            res = op.open(ws_req)
            print(f"[WS HEALTH] Status: {res.status}")
        except urllib.error.HTTPError as e:
            print(f"[WS HEALTH] Handshake Status: {e.code} ({e.reason})")
            if e.code == 101 or e.code == 400:
                print(" -> WebSocket server is active and responding!")

        # Check bus longpolling fallback /bus/websocket_worker_bundle
        bus_req = op.open(f"{url}/bus/websocket_worker_bundle?v=18.0-7")
        print(f"[BUS WORKER BUNDLE] Status: {bus_req.status} ({len(bus_req.read())} bytes)")

    except Exception as e:
        print(f"[ERROR] {e}")

test_websocket_health("http://localhost:8069", "odoo18", "admin", "zantatech@odoo", "LOCAL SERVER")
test_websocket_health("http://34.55.237.237:8069", "odoo18_db", "admin", "zantatech@odoo", "PRODUCTION SERVER")
