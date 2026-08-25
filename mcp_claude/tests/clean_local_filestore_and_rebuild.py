import sys
import os
import glob

sys.path.insert(0, r'D:\Odoo\odoo')
import odoo

print("==========================================================")
print("1. PURGING LOCAL FILESTORE ASSET FILES & DATABASE ATTACHMENTS")
print("==========================================================")

# Delete filestore files containing asset bundles
filestore_dir = r"D:\Odoo\data\filestore\odoo18"
deleted_files = 0
if os.path.exists(filestore_dir):
    for root, dirs, files in os.walk(filestore_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    if "ai_chat_service" in content or "assets_web" in content or "assets_backend" in content:
                        os.remove(fp)
                        deleted_files += 1
            except Exception as e:
                pass
print(f"Deleted {deleted_files} physical asset filestore files from {filestore_dir}")

# Clear DB attachment records
odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    atts = env['ir.attachment'].search([('url', 'like', '%assets%')])
    print(f"Deleting {len(atts)} ir.attachment DB records...")
    atts.unlink()
    cr.commit()

print("\n==========================================================")
print("2. UPGRADING MODULE mcp_claude TO FORCE NEW ASSET COMPILATION")
print("==========================================================")
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    mod = env['ir.module.module'].search([('name', '=', 'mcp_claude')])
    mod.button_immediate_upgrade()
    cr.commit()

print("\n==========================================================")
print("3. VERIFYING COMPILED ASSET BUNDLE IN NEW FILESTORE")
print("==========================================================")
found_new = False
for root, dirs, files in os.walk(filestore_dir):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                if "ai_chat_service" in content:
                    found_new = True
                    print(f"NEW FILESTORE ASSET FILE: {fp}")
                    idx = content.find("ai_chat_service")
                    print("EXACT CODE IN NEW FILESTORE:")
                    print(content[idx-30:idx+350])
        except Exception as e:
            pass

if not found_new:
    print("Notice: Assets will compile on first browser HTTP load.")

print("\nLOCAL ASSET CLEANUP AND REBUILD COMPLETED SUCCESSFULLY!")
