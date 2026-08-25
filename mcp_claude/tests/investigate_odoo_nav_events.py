import os
import re

odoo_web_path = r"D:\Odoo\odoo\addons\web\static\src"

print("=== SEARCHING ODOO 18 CORE WEB CLIENT FOR NAVIGATION & ACTION EVENTS ===")

search_terms = ["ACTION_MANAGER", "router", "currentController", "env.bus", "useBus"]

for root, dirs, files in os.walk(odoo_web_path):
    for f in files:
        if f.endswith(".js"):
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    if any(term in content for term in ["ACTION_MANAGER", "router.bus", "action_service"]):
                        for i, line in enumerate(content.splitlines(), 1):
                            if any(k in line for k in ["ACTION_MANAGER", "router", "bus.addEventListener", "bus.trigger"]):
                                print(f"FILE: {os.path.basename(fp)}:{i} -> {line.strip()[:150]}")
            except Exception:
                pass
