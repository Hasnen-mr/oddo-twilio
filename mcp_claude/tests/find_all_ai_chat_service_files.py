import os

print("=== SEARCHING ENTIRE D: DRIVE FOR ALL COPIES OF ai_chat_service.js ===")
for root, dirs, files in os.walk("D:\\"):
    # Skip venv and node_modules for speed
    if 'venv' in root or 'node_modules' in root or '.git' in root:
        continue
    for f in files:
        if f == "ai_chat_service.js":
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    print(f"\nFOUND FILE: {fp}")
                    print("   FILE SIZE:", len(content), "bytes")
                    for line in content.splitlines():
                        if "dependencies" in line:
                            print("   DEPENDENCIES LINE:", line.strip())
            except Exception as e:
                print("Error reading", fp, e)
