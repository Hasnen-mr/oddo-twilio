import subprocess

def run_git(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"D:\odoo-mcp")
    return res.stdout

print("==========================================================")
print("INSPECTING WORKING COMMIT 9aa0780 FILES")
print("==========================================================")

print("\n--- 9aa0780: ai_bubble_container.xml ---")
print(run_git("git show 9aa0780:mcp_claude/static/src/xml/ai_bubble_container.xml"))

print("\n--- 9aa0780: ai_bubble_container.js ---")
print(run_git("git show 9aa0780:mcp_claude/static/src/js/components/ai_bubble_container.js"))

print("\n--- 9aa0780: ai_bubble.scss ---")
print(run_git("git show 9aa0780:mcp_claude/static/src/scss/ai_bubble.scss"))
