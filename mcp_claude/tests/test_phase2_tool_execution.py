import sys
import json
import subprocess

print("==========================================================")
print("TESTING PHASE 2 TOOL CALLING & PROMPT BUILDER INTEGRATION")
print("==========================================================")

test_script = """
import sys
sys.path.insert(0, r"D:\\Odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\\odoo-mcp\\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    
    # 1. Test Prompt Builder Tool Serialization
    pb = env['mcp.ai.prompt.builder']
    tools = pb.get_available_tools()
    print(f'[PASS] Serialized {len(tools)} MCP tools for Claude API.')
    
    # Find odoo_search_opportunities
    opp_tool = [t for t in tools if t['name'] == 'odoo_search_opportunities']
    if opp_tool:
        print('[PASS] Found odoo_search_opportunities tool schema:')
        print(json.dumps(opp_tool[0], indent=2))
    
    # 2. Test Tool Execution directly via ToolRegistry
    from odoo.addons.mcp_claude.registry.tools import ToolRegistry
    res = ToolRegistry.execute_tool(env, 'odoo_search_opportunities', {'limit': 5})
    print('[PASS] Tool Execution Result:')
    print(json.dumps(res, indent=2, default=str))

    # 3. Test Session & Conversation creation
    service = env['mcp.ai.conversation.service']
    conv_data = service.get_or_create_conversation(scope='global')
    print('[PASS] Created Phase 2 Conversation:', conv_data)
"""

res = subprocess.run([r"D:\Odoo\venv\Scripts\python.exe", "-c", test_script], capture_output=True, text=True)
print("Exit code:", res.returncode)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
