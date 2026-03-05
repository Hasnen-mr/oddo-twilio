#!/bin/bash
# Run from repo root if __manifest__.py is at root (wrong). Creates odoo_twilio/ and moves files.
set -e
if [ -f "__manifest__.py" ] && [ ! -d "odoo_twilio" ]; then
  mkdir -p odoo_twilio
  for x in __manifest__.py __init__.py models views data security controllers wizard static README.md; do
    [ -e "$x" ] && mv "$x" odoo_twilio/
  done
  echo "Done. Commit and push branch 18.0."
fi
