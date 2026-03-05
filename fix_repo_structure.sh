#!/bin/bash
# Fix "No module found" for Odoo Apps Store: ensure one folder at repo root.
# Run this from the ROOT of your oddo-twilio repo (where .git is).
#
# If your repo has __manifest__.py at root (no odoo_twilio folder), this script
# creates odoo_twilio/ and moves all module files into it. Then commit and push.

set -e
MODULE_DIR="odoo_twilio"

# Already correct: odoo_twilio/ exists and contains __manifest__.py
if [ -d "$MODULE_DIR" ] && [ -f "$MODULE_DIR/__manifest__.py" ]; then
  echo "Structure OK: $MODULE_DIR/ exists with __manifest__.py"
  exit 0
fi

# Wrong: __manifest__.py at current dir (repo root) – need to wrap in folder
if [ -f "__manifest__.py" ]; then
  echo "Creating $MODULE_DIR/ and moving module files into it..."
  mkdir -p "$MODULE_DIR"
  for item in __manifest__.py __init__.py models views data security controllers wizard static README.md; do
    [ -e "$item" ] && mv "$item" "$MODULE_DIR/"
  done
  echo "Done. Commit and push:"
  echo "  git add -A && git commit -m 'Fix: module in folder at root for Odoo Apps Store' && git push origin 18.0"
  exit 0
fi

echo "Error: Run this from the repo root (where .git is). No __manifest__.py found here."
exit 1
