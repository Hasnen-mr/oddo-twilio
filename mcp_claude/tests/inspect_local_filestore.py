import os

for root, dirs, files in os.walk(r"D:\Odoo\data"):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                if "/* /mcp_claude/static/src/js/ai_chat_service.js */" in content:
                    print("\n=======================================================")
                    print("EXACT FILE IN ODOO DATA DIR:", fp)
                    print("=======================================================")
                    idx = content.find("/* /mcp_claude/static/src/js/ai_chat_service.js */")
                    print(content[idx:idx+800])
        except Exception as e:
            pass
