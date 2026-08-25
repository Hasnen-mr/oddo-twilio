import os

print("=== SEARCHING D:\\Odoo\\data FOR ALL COPIES OF ai_chat_service AND ASSETS ===")
for root, dirs, files in os.walk(r"D:\Odoo\data"):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                if "ai_chat_service" in content:
                    print(f"\nFOUND IN DATA DIR: {fp}")
                    print("   FILE SIZE:", len(content), "bytes")
                    for line in content.splitlines():
                        if "dependencies" in line or "ai_chat_service" in line:
                            print("   LINE:", line[:200])
        except Exception as e:
            pass
