import os
import re

addons_dir = r"D:\odoo-mcp\mcp_claude\static\src\js"
manifest_path = r"D:\odoo-mcp\mcp_claude\__manifest__.py"

print("==========================================================================")
print("COMPREHENSIVE ODOO 18 JS MODULE DEPENDENCY & IMPORT AUDIT")
print("==========================================================================")

js_files = []
for root, dirs, files in os.walk(addons_dir):
    for f in files:
        if f.endswith(".js"):
            js_files.append(os.path.join(root, f))

print(f"Found {len(js_files)} JS files in mcp_claude/static/src/js:")
for jf in js_files:
    rel_p = os.path.relpath(jf, r"D:\odoo-mcp")
    print(f" - {rel_p}")

print("\n--------------------------------------------------------------------------")
print("1. AUDITING MODULE HEADERS & ALIAS DECLARATIONS")
print("--------------------------------------------------------------------------")

module_defines = {}
for jf in js_files:
    rel_p = os.path.relpath(jf, r"D:\odoo-mcp\mcp_claude\static\src\js").replace("\\", "/")
    expected_alias = f"@mcp_claude/js/{rel_p[:-3]}"
    
    with open(jf, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    first_line = lines[0].strip() if lines else ""
    print(f"\nFile: mcp_claude/static/src/js/{rel_p}")
    print(f" Header line 1: '{first_line}'")
    print(f" Default Odoo 18 Module Name: '{expected_alias}'")

print("\n--------------------------------------------------------------------------")
print("2. RECURSIVE IMPORT TRACE & DEPENDENCY GRAPH")
print("--------------------------------------------------------------------------")

import_pattern = re.compile(r'import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+["\']([^"\']+)["\']')

for jf in js_files:
    rel_p = os.path.relpath(jf, r"D:\odoo-mcp\mcp_claude\static\src\js").replace("\\", "/")
    print(f"\n[MODULE] {rel_p}")
    with open(jf, "r", encoding="utf-8") as f:
        content = f.read()
    
    matches = import_pattern.findall(content)
    for destructured, default_imp, imp_path in matches:
        symbols = (destructured or default_imp).strip()
        print(f"   -> imports ({symbols}) from '{imp_path}'")

print("\n--------------------------------------------------------------------------")
print("3. CHECKING MANIFEST ASSET ORDER IN __manifest__.py")
print("--------------------------------------------------------------------------")

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest_text = f.read()

print("Assets listed in __manifest__.py web.assets_backend:")
assets_backend_idx = manifest_text.find("'web.assets_backend': [")
if assets_backend_idx != -1:
    assets_block = manifest_text[assets_backend_idx:manifest_text.find("]", assets_backend_idx)]
    for line in assets_block.splitlines():
        if ".js" in line or ".xml" in line or ".scss" in line:
            print("  ", line.strip())
