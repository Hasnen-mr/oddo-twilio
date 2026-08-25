import subprocess

def run_git(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"D:\odoo-mcp")
    return res.stdout

print("==========================================================")
print("PREVIOUS WORKING COMMIT 1b6089d FILES")
print("==========================================================")

print("\n--- 1b6089d: ai_bubble_container.xml ---")
print(run_git("git show 1b6089d:mcp_claude/static/src/xml/ai_bubble_container.xml"))

print("\n--- 1b6089d: ai_bubble_container.js ---")
print(run_git("git show 1b6089d:mcp_claude/static/src/js/components/ai_bubble_container.js"))

print("\n--- 1b6089d: ai_chat_window.xml ---")
print(run_git("git show 1b6089d:mcp_claude/static/src/xml/ai_chat_window.xml"))

print("\n--- 1b6089d: ai_chat_window.js ---")
print(run_git("git show 1b6089d:mcp_claude/static/src/js/components/ai_chat_window.js"))

print("\n--- 1b6089d: ai_bubble.scss ---")
print(run_git("git show 1b6089d:mcp_claude/static/src/scss/ai_bubble.scss"))
