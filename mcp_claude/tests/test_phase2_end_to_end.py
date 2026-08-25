import sys
import json
import subprocess

print("==========================================================")
print("PHASE 2 STRICT LOCALHOST END-TO-END VERIFICATION HARNESS")
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
    
    print("\\n--- 1. Testing API Key Security & Unconfigured Message ---")
    provider = env['mcp.ai.provider.claude']
    missing_key_res = provider.generate_completion({'messages': [{'role': 'user', 'content': 'hi'}]})
    print("[PASS] Missing Key Response:", missing_key_res.get('content'))
    assert "Claude API Key is not configured" in missing_key_res.get('content')
    
    print("\\n--- 2. Testing Dynamic Tool Discovery & Formatting ---")
    pb = env['mcp.ai.prompt.builder']
    tools = pb.get_available_tools()
    print(f"[PASS] Dynamic Tool Discovery returned {len(tools)} tools from ToolRegistry.")
    
    partner_tool = next((t for t in tools if t['name'] == 'odoo_search_partners'), None)
    assert partner_tool is not None
    assert 'input_schema' in partner_tool
    assert partner_tool['name'] == 'odoo_search_partners'
    print("[PASS] odoo_search_partners tool schema validated:")
    print(json.dumps(partner_tool, indent=2))
    
    print("\\n--- 3. Testing Direct MCP Odoo Data Retrieval ---")
    from odoo.addons.mcp_claude.registry.tools import ToolRegistry
    tool_res = ToolRegistry.execute_tool(env, 'odoo_search_partners', {'limit': 5})
    assert tool_res.get('success') is True
    print(f"[PASS] Tool Execution retrieved {tool_res.get('count')} records from res.partner.")
    if tool_res.get('records'):
        sample = tool_res.get('records')[0]
        print(f"[PASS] Sample Contact Record: ID #{sample.get('id')} - {sample.get('name')} <{sample.get('email')}>")
    
    print("\\n--- 4. Testing Permission Enforcement (mcp.model.rule) ---")
    rule = env['mcp.model.rule'].search([('model_id.model', '=', 'res.partner')], limit=1)
    can_read = env['mcp.model.rule'].check_permission('res.partner', 'search')
    print(f"[PASS] mcp.model.rule permission check for res.partner search: {can_read}")
    assert can_read is True
        
    print("\\n--- 5. Testing Phase 1 Regression (Init Chat & Scope Switch) ---")
    conv_service = env['mcp.ai.conversation.service']
    global_conv = conv_service.get_or_create_conversation(scope='global')
    record_conv = conv_service.get_or_create_conversation(scope='record', model_name='res.partner', res_id=3)
    
    assert global_conv['scope'] == 'global'
    assert record_conv['scope'] == 'record'
    print("[PASS] Global Scope Thread:", global_conv['title'], "| ID:", global_conv['conversation_id'])
    print("[PASS] Record Scope Thread:", record_conv['title'], "| ID:", record_conv['conversation_id'])
    
    print("\\n==========================================================")
    print("ALL LOCALHOST VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==========================================================")
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
