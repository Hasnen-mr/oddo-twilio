import sys
import json
import subprocess

print("==========================================================")
print("RUNNING REAL PHASE 2 END-TO-END TEST (LOCALHOST ONLY)")
print("==========================================================")

test_script = """
import sys
import json
import os
sys.path.insert(0, r"D:\\Odoo\\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\\odoo-mcp\\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    
    # 1. Check/Configure API Key on mcp.server.config securely
    config = env['mcp.server.config'].sudo().search([], limit=1)
    if not config:
        config = env['mcp.server.config'].sudo().create({'name': 'Default MCP Settings'})
    
    api_key = config.claude_api_key or env['ir.config_parameter'].sudo().get_param('mcp_claude.claude_api_key', None) or os.environ.get("ANTHROPIC_API_KEY", None)
    
    if not api_key:
        print("[NOTICE] No Claude API key currently found in database or environment.")
        print("Please configure your API key in mcp.server.config via Odoo Settings or set ANTHROPIC_API_KEY environment variable.")
        sys.exit(0)
        
    config.sudo().write({'claude_api_key': api_key})
    print(f"[SECURE] API Key loaded into mcp.server.config (Length: {len(api_key)}, Prefix: {api_key[:8]}... mask: ********)")

    # 2. Test Connection Action
    conn_res = config.action_test_claude_connection()
    print("[CONN TEST]", conn_res.get('params', {}).get('title'), "-", conn_res.get('params', {}).get('message'))

    # 3. Create Conversation and process user prompt
    conv_service = env['mcp.ai.conversation.service']
    conv = env['mcp.ai.conversation'].sudo().create({
        'name': 'Phase 2 Real E2E Test Thread',
        'scope_type': 'global',
        'state': 'idle',
        'user_id': 1
    })
    
    prompt = "Show me the 5 latest contacts."
    print(f"\\n--- Running User Prompt: '{prompt}' ---")
    
    result = conv_service.process_user_prompt(conv.id, prompt)
    
    print("\\n================ E2E PIPELINE EXECUTION TRACE ================")
    print("Conversation ID:", conv.id)
    print("Execution Status:", result.get("status"))
    print("Tool Executed:", result.get("tool_executed"))
    print("Tool Name:", result.get("tool_name"))
    print("Tool Arguments:", result.get("tool_args"))
    print("Odoo Records Retrieved Count:", len(result.get("tool_result", {}).get("records", [])) if isinstance(result.get("tool_result"), dict) else "N/A")
    
    print("\\n--- Retrived Contact Records Sample ---")
    if isinstance(result.get("tool_result"), dict) and "records" in result.get("tool_result"):
        for p in result.get("tool_result", {}).get("records", [])[:5]:
            print(f"  - Record #{p.get('id')}: {p.get('name')} <{p.get('email') or 'no-email'}>")

    print("\\n--- Final Natural Language Claude Response ---")
    print(result.get("response"))
    print("==============================================================")

    # 4. Security Audit on DB records
    messages = env['mcp.ai.message'].sudo().search([('conversation_id', '=', conv.id)])
    key_leaked = False
    for m in messages:
        if api_key in (m.content or ""):
            key_leaked = True
            
    print("\\n--- SECURITY AUDIT ---")
    print("API Key present in DB messages table:", "LEAK DETECTED!" if key_leaked else "PASS (0 leaks found)")
    print("API Key present in API return payload:", "LEAK DETECTED!" if api_key in json.dumps(result) else "PASS (0 leaks found)")
    
    assert not key_leaked, "SECURITY VIOLATION: API Key found in database messages!"
    assert api_key not in json.dumps(result), "SECURITY VIOLATION: API Key found in API return payload!"
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
