#!/bin/bash
# Run this script at the ROOT of your oddo-twilio repo if Odoo Apps Store
# reports "No module found". It creates a folder odoo_twilio/ and moves
# all module files into it so the store sees one module at root.
# Usage: from repo root, run: ./fix_repo_structure.sh  (or bash fix_repo_structure.sh)

set -e
MODULE_DIR="odoo_twilio"

if [ -d "$MODULE_DIR" ] && [ -f "$MODULE_DIR/__manifest__.py" ]; then
  echo "Structure already correct: $MODULE_DIR/ exists with __manifest__.py."
  exit 0
fi

if [ ! -f "__manifest__.py" ]; then
  echo "Run this script from the root of the oddo-twilio repository (where __manifest__.py is)."
  exit 1
fi

echo "Creating $MODULE_DIR/ and moving module files into it..."
mkdir -p "$MODULE_DIR"
for item in __manifest__.py __init__.py models views data security controllers wizard static README.md; do
  [ -e "$item" ] && mv "$item" "$MODULE_DIR/"
done
echo "Done. Repo root should now contain only: $MODULE_DIR/"
ls -la
ls -la "$MODULE_DIR/"
