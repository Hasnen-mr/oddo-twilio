import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

print("==========================================================")
print("FETCH LIVE ASSET BUNDLE FROM WEB CLIENT & CHECK DEPENDENCIES")
print("==========================================================")

curl_script = '''import urllib.request, json, re

req = urllib.request.urlopen("http://localhost:8069/web")
html = req.read().decode("utf-8", errors="ignore")

asset_urls = re.findall(r"/web/assets/[^\s\"']+\.js", html)
print("ASSET URLS FOUND IN HTML:", asset_urls)

for url in asset_urls:
    full_url = "http://localhost:8069" + url
    try:
        js_req = urllib.request.urlopen(full_url)
        js_text = js_req.read().decode("utf-8", errors="ignore")
        if "ai_chat_service" in js_text:
            print(f"\\nFOUND ai_chat_service IN LIVE ASSET URL: {url}")
            for part in js_text.split(";"):
                if "ai_chat_service" in part:
                    print("   LIVE SERVED JS CODE:", part[:300])
    except Exception as e:
        print(f"Error fetching {url}: {e}")
'''

with open(r"D:\odoo-mcp\check_live_assets.py", "w", encoding="utf-8") as f:
    f.write(curl_script)

subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\check_live_assets.py {target}:/tmp/check_live_assets.py', shell=True)
run_cmd = 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/check_live_assets.py'
res2 = subprocess.run(['ssh', '-i', ssh_key, target, run_cmd], capture_output=True, text=True)
print(res2.stdout)
if res2.stderr:
    print("[STDERR]", res2.stderr)
