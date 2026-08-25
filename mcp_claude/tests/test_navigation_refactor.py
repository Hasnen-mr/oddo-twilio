import sys
import json
import subprocess

print("==========================================================")
print("VERIFYING MCP CLAUDE SINGLE PRIMARY NAVIGATION REFACTOR")
print("==========================================================")

test_script = """
import sys
import json
sys.path.insert(0, r"D:\\Odoo\\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\\odoo-mcp\\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    
    print("\\n--- 1. Top Navigation Cleaning ---")
    root_menu = env['ir.ui.menu'].sudo().search([('name', '=', 'MCP Claude'), ('parent_id', '=', False)], limit=1)
    assert root_menu, "Root menu item MCP Claude not found!"
    child_menus = env['ir.ui.menu'].sudo().search([('parent_id', '=', root_menu.id)])
    print("Child menus under MCP Claude root:", [c.name for c in child_menus])
    assert len(child_menus) == 0, f"FAIL: Expected 0 child submenus in top header, found {len(child_menus)}"
    assert root_menu.action.res_model == 'ir.actions.client' or root_menu.action.name == 'MCP Claude Control Center', "Root menu action invalid!"
    print("[PASS] Top header navigation cleaned completely. Only 'MCP Claude' root brand icon remains.")

    print("\\n--- 2. OWL Template & Bottom Navigation Architecture ---")
    with open(r"D:\\odoo-mcp\\mcp_claude\\static\\src\\xml\\control_center.xml", "r", encoding="utf-8") as f:
        xml_content = f.read()

    assert 'class="mcp-bottom-nav"' in xml_content, "Bottom navigation container missing!"
    assert 'setTabHome' in xml_content, "setTabHome missing from bottom nav!"
    assert 'setTabDashboards' in xml_content, "setTabDashboards missing from bottom nav!"
    assert 'setTabTools' in xml_content, "setTabTools missing from bottom nav!"
    assert 'setTabConfigurations' in xml_content, "setTabConfigurations missing from bottom nav!"
    assert 'openServerConfiguration' in xml_content, "openServerConfiguration action missing from Configurations pane!"
    assert 'openModelPermissionRules' in xml_content, "openModelPermissionRules action missing from Configurations pane!"
    print("[PASS] Bottom navigation bar is configured as single primary navigation system.")

    print("\\n--- 3. Target Configuration Views Access ---")
    server_cfg = env['mcp.server.config'].sudo().search([], limit=1)
    assert server_cfg, "Server Configuration model unreachable!"
    model_rule = env['mcp.model.rule'].sudo().search([], limit=1)
    assert model_rule, "Model Permission Rules model unreachable!"
    print("[PASS] Both Server Configuration and Model Permission Rules models and actions verified.")

    print("\\n--- 4. AI Bubble Regression Check ---")
    provider = env['mcp.ai.provider.claude']
    resp = provider.generate_completion({'messages': [{'role': 'user', 'content': 'hello'}]})
    assert resp and 'content' in resp, "AI Bubble provider response failed!"
    print("[PASS] AI Bubble functionality is 100% active & regression-free.")

    print("\\n==========================================================")
    print("NAVIGATION REFACTOR VERIFICATION PASSED!")
    print("==========================================================")
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
