import urllib.request
import json
import http.cookiejar
import re

print("==========================================================================")
print("RUNTIME ASSET BUNDLE DEEP INSPECTION & MODULE RESOLUTION AUDIT")
print("==========================================================================")

url = "http://34.55.237.237:8069"
db = "odoo18_db"
login = "admin"
pwd = "zantatech@odoo"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Authenticate
auth_payload = {'jsonrpc': '2.0', 'id': 1, 'params': {'db': db, 'login': login, 'password': pwd}}
req_auth = urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps(auth_payload).encode(), headers={'Content-Type': 'application/json'})
op.open(req_auth)

# 2. Fetch main web client HTML to extract exact asset bundle URLs
html = op.open(f"{url}/web").read().decode('utf-8')
asset_js_urls = [line[line.find('/web/assets/'):line.find('.js', line.find('/web/assets/'))+3] for line in html.splitlines() if '/web/assets/' in line and '.js' in line]

print("Found Asset JS Bundles loaded on Odoo Web Client:")
for u in asset_js_urls:
    print(f" - {u}")

# 3. Read compiled JS bundle
backend_bundle_url = [u for u in asset_js_urls if 'web.assets_web' in u or 'web.assets_backend' in u][0]
bundle_content = op.open(f"{url}{backend_bundle_url}").read().decode('utf-8', errors='ignore')

print(f"\nAnalyzing bundle: {backend_bundle_url} ({len(bundle_content)} bytes)")

expected_modules = [
    "@mcp_claude/js/registries/ai_context_provider_registry",
    "@mcp_claude/js/registries/ai_renderer_registry",
    "@mcp_claude/js/providers/core_context_providers",
    "@mcp_claude/js/ai_chat_service",
    "@mcp_claude/js/components/ai_bubble_trigger",
    "@mcp_claude/js/components/ai_chat_skeleton",
    "@mcp_claude/js/components/ai_chat_window",
    "@mcp_claude/js/components/ai_bubble_container",
]

print("\n--------------------------------------------------------------------------")
print("STEP 1 & 2: VERIFYING EXACT MODULE DEFINITIONS AND ALIASES IN BUNDLE")
print("--------------------------------------------------------------------------")

for em in expected_modules:
    clean_path = em.replace("@mcp_claude/js/", "mcp_claude/static/src/js/") + ".js"
    in_bundle = (em in bundle_content) or (clean_path in bundle_content)
    
    pos = bundle_content.find(em)
    if pos == -1:
        pos = bundle_content.find(clean_path)
    
    if in_bundle:
        print(f" [PRESENT IN BUNDLE] {em} (offset: {pos})")
    else:
        print(f" [ABSENT FROM BUNDLE!] {em}")

print("\n--------------------------------------------------------------------------")
print("STEP 3 & 4: INSPECTING COMPILED BUNDLE CODE FOR DEFINE / IMPORT SYNTAX")
print("--------------------------------------------------------------------------")

# Extract every module definition for mcp_claude in bundle
defines = re.findall(r'define\s*\(\s*["\'](@mcp_claude/[^"\']+)["\']\s*,\s*\[([^\]]*)\]', bundle_content)
if not defines:
    # Try matching Odoo 18 ES module defines
    defines = re.findall(r'/\* @odoo-module alias=([^\s\*]+) \*/', bundle_content)

print(f"Found {len(defines)} explicit module defines in compiled JS bundle:")
for d in defines:
    print("  ", d)

print("\n--------------------------------------------------------------------------")
print("SNIPPET INSPECTION OF AIChatWindow & AIChatSkeleton DEFINITIONS")
print("--------------------------------------------------------------------------")

idx_sk = bundle_content.find("AIChatSkeleton")
if idx_sk != -1:
    print("\n[AIChatSkeleton Compiled Code]:")
    print(bundle_content[max(0, idx_sk-100):idx_sk+400])

idx_win = bundle_content.find("AIChatWindow")
if idx_win != -1:
    print("\n[AIChatWindow Compiled Code]:")
    print(bundle_content[max(0, idx_win-100):idx_win+400])

idx_ctr = bundle_content.find("AIBubbleContainer")
if idx_ctr != -1:
    print("\n[AIBubbleContainer Compiled Code]:")
    print(bundle_content[max(0, idx_ctr-100):idx_ctr+400])
