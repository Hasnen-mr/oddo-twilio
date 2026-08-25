import urllib.request
import json
import http.cookiejar
import re
import os

print("==========================================================================")
print("DEEP ASSET TRACER & RUNTIME DEPENDENCY DIAGNOSTIC")
print("==========================================================================")

# 1. Search local filesystem for ANY file containing 'ai_chat_service' or 'dependencies' with 'rpc'
search_dirs = [
    r"D:\odoo-mcp",
    r"D:\Odoo\odoo\addons",
    r"D:\Odoo\custom_addons",
]

print("\n--- 1. SEARCHING LOCAL FILESYSTEM FOR ALL OCCURRENCES ---")
for sdir in search_dirs:
    if not os.path.exists(sdir): continue
    for root, dirs, files in os.walk(sdir):
        for f in files:
            if f.endswith('.js') or f.endswith('.py') or f.endswith('.xml'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as file:
                        content = file.read()
                        if 'ai_chat_service' in content:
                            print(f"\nFILE: {fp}")
                            for i, line in enumerate(content.splitlines(), 1):
                                if any(k in line for k in ['dependencies', 'ai_chat_service', 'rpc', 'user', 'add(']):
                                    print(f"   Line {i}: {line.strip()}")
                except Exception as e:
                    pass

# 2. Login to local server (if running) and remote production server
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

login_req = {'jsonrpc': '2.0', 'id': 1, 'params': {'db': 'odoo18', 'login': 'admin', 'password': 'admin'}}
try:
    r1 = opener.open(urllib.request.Request('http://localhost:8069/web/session/authenticate', data=json.dumps(login_req).encode(), headers={'Content-Type': 'application/json'}))
    print("\n--- 2. LOCAL SERVER AUTHENTICATION SUCCESSFUL ---")
    web_html = opener.open('http://localhost:8069/web').read().decode('utf-8', errors='ignore')
    
    asset_urls = re.findall(r'src=["\'](/web/assets/[^"\']+\.js)', web_html)
    print("LOCAL WEB ASSET URLS IN HTML:", asset_urls)
    
    for url in asset_urls:
        full_url = 'http://localhost:8069' + url
        js_content = opener.open(full_url).read().decode('utf-8', errors='ignore')
        if 'ai_chat_service' in js_content:
            print(f"\nFOUND 'ai_chat_service' IN LOCAL BUNDLE: {url}")
            match = re.search(r'aiChatService\s*=\s*\{[^}]+\}', js_content)
            if match:
                print("   EXACT OBJECT IN BUNDLE:", match.group(0))
            else:
                idx = js_content.find('ai_chat_service')
                print("   CODE SNIPPET:", js_content[max(0, idx-50):idx+300])

except Exception as e:
    print("Local server check exception:", e)
