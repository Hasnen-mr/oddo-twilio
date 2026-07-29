#!/usr/bin/env bash
# Odoo 14–16: use <tree> views and tree view_mode (list renamed in Odoo 17+).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILES=(
    "$ROOT/twilio_dialer/views/twilio_config_views.xml"
    "$ROOT/twilio_dialer/views/twilio_sms_views.xml"
    "$ROOT/twilio_dialer/views/twilio_call_log_views.xml"
    "$ROOT/twilio_dialer/views/twilio_dialer_views.xml"
    "$ROOT/twilio_dialer/wizard/fetch_sms_wizard.py"
    "$ROOT/twilio_dialer/wizard/fetch_calls_wizard.py"
)

for file in "${FILES[@]}"; do
    sed -i '' \
        -e 's/view_mode">list,form/view_mode">tree,form/g' \
        -e 's/"view_mode": "list"/"view_mode": "tree"/g' \
        -e 's/<list /<tree /g' \
        -e 's/<\/list>/<\/tree>/g' \
        "$file"
done
