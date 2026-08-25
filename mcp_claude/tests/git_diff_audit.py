import subprocess

def run_git(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"D:\odoo-mcp")
    return res.stdout

print("==========================================================")
print("GIT REGRESSION DIFF ANALYSIS (1b6089d vs 774d603)")
print("==========================================================")

print("\n--- DIFF IN ai_bubble_container.xml ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/xml/ai_bubble_container.xml"))

print("\n--- DIFF IN ai_bubble_container.js ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/js/components/ai_bubble_container.js"))

print("\n--- DIFF IN ai_bubble_trigger.js ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/js/components/ai_bubble_trigger.js"))

print("\n--- DIFF IN ai_bubble.scss ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/scss/ai_bubble.scss"))

print("\n--- DIFF IN ai_chat_window.xml ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/xml/ai_chat_window.xml"))

print("\n--- DIFF IN ai_chat_window.js ---")
print(run_git("git diff 1b6089d 774d603 -- mcp_claude/static/src/js/components/ai_chat_window.js"))
