import urllib.request
import json
import http.cookiejar
import os

print("=== 1. AUTHENTICATING AND TRIGGERING FRESH HTTP ASSET COMPILATION ===")

cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

login_req = {'jsonrpc': '2.0', 'id': 1, 'params': {'db': 'odoo18', 'login': 'admin', 'password': 'admin'}}
r1 = opener.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps(login_req).encode(), headers={'Content-Type': 'application/json'}))
print("LOGIN RESULT:", json.loads(r1.read().decode())['result']['uid'])

web_html = opener.open('http://localhost:8069/web').read().decode('utf-8', errors='ignore')
print("WEB PAGE LOADED SUCCESSFULLY!")

print("\n=== 2. INSPECTING FRESHLY COMPILED FILESTORE ASSET FILE ===")
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
    print("Asset not found in filestore, checking HTTP asset URLs...")
    for line in web_html.splitlines():
        if "/web/assets/" in line and ".js" in line:
            start = line.find("/web/assets/")
            end = line.find(".js", start)
            if start != -1 and end != -1:
                url = "http://localhost:8069" + line[start:end+3]
                js = opener.open(url).read().decode('utf-8', errors='ignore')
                if 'ai_chat_service' in js:
                    print("FOUND IN HTTP ASSET URL:", url)
                    i = js.find("aiChatService=")
                    print(js[i:i+250])
