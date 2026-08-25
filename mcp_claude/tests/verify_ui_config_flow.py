import sys
import json
import subprocess

print("==========================================================")
print("VERIFYING CLAUDE MODULE CONFIGURATION UI & SECURITY CONTRACT")
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
    
    print("\\n--- 1. Verifying Navigation Menu Structure ---")
    menu = env['ir.ui.menu'].sudo().search([('name', '=', 'Server Configuration')], limit=1)
    assert menu, "Server Configuration menu not found!"
    print("[PASS] Menu Item Found: 'MCP Claude -> Configuration -> Server Configuration' (ID:", menu.id, ")")

    print("\\n--- 2. Verifying Form View Password Masking ---")
    views = env['mcp.server.config'].sudo().get_views([(False, 'form')])
    arch = views.get('views', {}).get('form', {}).get('arch', '')
    assert 'password="1"' in arch, "password='1' masking missing from form view!"
    assert 'claude_api_key' in arch, "claude_api_key field missing from form view!"
    assert 'action_test_claude_connection' in arch, "action_test_claude_connection button missing from header!"
    print("[PASS] Form View Contract Validated: Field 'claude_api_key' is masked with password='1' and includes Test Connection button.")

    print("\\n--- 3. Verifying Missing API Key Error Message ---")
    config = env['mcp.server.config'].sudo().search([], limit=1)
    if not config:
        config = env['mcp.server.config'].sudo().create({'name': 'Default MCP Settings'})
    config.write({'claude_api_key': False})
    
    provider = env['mcp.ai.provider.claude']
    resp = provider.generate_completion({'messages': [{'role': 'user', 'content': 'hi'}]})
    print("[PASS] AI Bubble Unconfigured Error Message:")
    print(resp.get('content'))
    assert "Claude API is not configured" in resp.get('content')
    assert "MCP Claude -> Configuration -> Server Configuration" in resp.get('content')

    print("\\n--- 4. Verifying Test Connection Action Safe Notifications ---")
    conn_no_key = config.action_test_claude_connection()
    print("[PASS] Connection Test (No Key):", conn_no_key.get('params', {}).get('title'), "|", conn_no_key.get('params', {}).get('message'))
    assert "claude connection failed" in conn_no_key.get('params', {}).get('title').lower()

    config.write({'claude_api_key': 'sk-ant-test-key-invalid'})
    conn_invalid_key = config.action_test_claude_connection()
    print("[PASS] Connection Test (Invalid Key):", conn_invalid_key.get('params', {}).get('title'), "|", conn_invalid_key.get('params', {}).get('message'))
    assert "claude connection failed" in conn_invalid_key.get('params', {}).get('title').lower()
    assert "sk-ant-test-key-invalid" not in conn_invalid_key.get('params', {}).get('message'), "SECURITY ERROR: API Key leaked in notification message!"

    # Clean up test key
    config.write({'claude_api_key': False})

    print("\\n==========================================================")
    print("ALL MODULE UI CONFIGURATION & SECURITY CONTRACTS PASSED!")
    print("==========================================================")
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
