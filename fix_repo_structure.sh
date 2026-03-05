#!/bin/bash
# Run from repo root if __manifest__.py is at root (wrong). Creates twilio_dialer/ and moves files.
set -e
if [ -f "__manifest__.py" ] && [ ! -d "twilio_dialer" ]; then
  mkdir -p twilio_dialer
  for x in __manifest__.py __init__.py models views data security controllers wizard static README.md; do
    [ -e "$x" ] && mv "$x" twilio_dialer/
  done
  echo "Done. Commit and push branch 18.0."
fi
