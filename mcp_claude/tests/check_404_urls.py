import urllib.request
import json
import http.cookiejar

def audit_404(url, db, user, pwd, label):
    print(f"==========================================================")
    print(f"AUDITING 404 RESOURCES ON {label} ({url})")
    print(f"==========================================================")
    try:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        
        # Authenticate
        auth_res = op.open(urllib.request.Request(f"{url}/web/session/authenticate", data=json.dumps({'jsonrpc':'2.0','id':1,'params':{'db':db,'login':user,'password':pwd}}).encode(), headers={'Content-Type':'application/json'}))
        print(f"[AUTH] Status: {auth_res.status}")
        
        # Fetch /web
        web_html = op.open(f"{url}/web").read().decode('utf-8')
        
        # Extract all script and link stylesheet src/href attributes
        import re
        asset_paths = re.findall(r'(?:src|href)=["\'](/[^"\']+)["\']', web_html)
        
        print(f"Testing {len(asset_paths)} asset resources extracted from HTML:")
        bad_count = 0
        for path in asset_paths:
            full_u = f"{url}{path}"
            try:
                r = op.open(full_u)
                if r.status != 200:
                    print(f"  [BAD {r.status}] {path}")
                    bad_count += 1
            except urllib.error.HTTPError as e:
                print(f"  [FAIL {e.code}] {path}")
                bad_count += 1
            except Exception as e:
                print(f"  [ERROR] {path} -> {e}")
                bad_count += 1
        
        if bad_count == 0:
            print(f"[PASS] All {len(asset_paths)} web assets returned 200 OK! Zero 404 errors found in assets bundle.\n")
        else:
            print(f"[WARNING] Found {bad_count} failing resource paths!\n")

    except Exception as e:
        print(f"[ERROR] Audit failed: {e}\n")

audit_404("http://localhost:8069", "odoo18", "admin", "zantatech@odoo", "LOCAL SERVER")
audit_404("http://34.55.237.237:8069", "odoo18_db", "admin", "zantatech@odoo", "PRODUCTION SERVER")
