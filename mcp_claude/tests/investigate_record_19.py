import sys
sys.path.insert(0, r"D:\Odoo\odoo")
import odoo
import odoo.tools

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    print("==========================================================")
    print("INSPECTING RECORD #19 ACROSS ODOO MODELS")
    print("==========================================================")
    
    models_to_check = [
        "twilio.dialer.dashboard",
        "mcp.ai.conversation",
        "mcp.ai.message",
        "mcp.ai.session",
        "mcp.audit.log"
    ]
    
    for mname in models_to_check:
        if mname in env:
            rec = env[mname].sudo().browse(19)
            if rec.exists():
                print(f"\n---> Found Record #19 in model: {mname}")
                read_data = rec.read()[0]
                cleaned = {}
                for k, v in read_data.items():
                    val_str = str(v)
                    if len(val_str) > 200:
                        cleaned[k] = val_str[:200] + f"... (total len: {len(val_str)})"
                    else:
                        cleaned[k] = v
                print("Fields & Values:")
                import json
                print(json.dumps(cleaned, indent=2, default=str))
            else:
                print(f"Model '{mname}': Record #19 does not exist.")
