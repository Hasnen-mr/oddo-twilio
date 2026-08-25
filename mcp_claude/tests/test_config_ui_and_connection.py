import sys
import json
import subprocess

print("==========================================================")
print("TESTING CLAUDE MODULE CONFIGURATION UI & PROVIDER INTEGRATION")
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
    
    print("\\n--- 1. Testing Unconfigured API Key Behavior ---")
    config = env['mcp.server.config'].sudo().search([], limit=1)
    if not config:
        config = env['mcp.server.config'].sudo().create({'name': 'Default MCP Settings'})
    
    # Clear any temporary keys for test
    config.write({'claude_api_key': False})
    env['ir.config_parameter'].sudo().set_param('mcp_claude.claude_api_key', False)
    
    provider = env['mcp.ai.provider.claude']
    unconfig_res = provider.generate_completion({'messages': [{'role': 'user', 'content': 'hi'}]})
    print("[PASS] Unconfigured message:", unconfig_res.get('content'))
    assert "Claude API is not configured. An administrator can add the Anthropic API key" in unconfig_res.get('content')
    
    print("\\n--- 2. Testing Test Connection Action with No Key ---")
    no_key_action = config.action_test_claude_connection()
    print("[PASS] Test connection action returned:", no_key_action.get('params', {}).get('title'))
    assert no_key_action.get('params', {}).get('title') == 'Connection Test Failed'

    print("\\n--- 3. Testing Test Connection Action with Dummy Invalid Key ---")
    config.write({'claude_api_key': 'sk-ant-invalid-test-key'})
    dummy_key_action = config.action_test_claude_connection()
    print("[PASS] Test connection action returned:", dummy_key_action.get('params', {}).get('title'))
    print("Notification message:", dummy_key_action.get('params', {}).get('message'))
    assert 'API Error' in dummy_key_action.get('params', {}).get('message') or '401' in dummy_key_action.get('params', {}).get('message')

    print("\\n--- 4. Testing get_claude_api_key() Single Source of Truth ---")
    resolved_key = env['mcp.server.config'].get_claude_api_key()
    assert resolved_key == 'sk-ant-invalid-test-key'
    print("[PASS] get_claude_api_key() correctly retrieved configured key from mcp.server.config")

    # Clean up test key
    config.write({'claude_api_key': False})
    
    print("\\n==========================================================")
    print("ALL MODULE CONFIGURATION TESTS PASSED SUCCESSFULLY!")
    print("==========================================================")
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
