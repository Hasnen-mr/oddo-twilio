#!/usr/bin/env bash
# Twilio Dialer — macOS / Linux installer
# Finds Odoo, copies the module into custom addons, installs Python deps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODULE_SRC="$REPO_ROOT/twilio_dialer"
REQ_FILE="$REPO_ROOT/requirements.txt"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

info()  { echo "${CYAN}==>${NC} $*"; }
ok()    { echo "${GREEN}OK:${NC} $*"; }
warn()  { echo "${YELLOW}NOTE:${NC} $*"; }
fail()  { echo "${RED}ERROR:${NC} $*" >&2; exit 1; }

echo
echo "=============================================="
echo "  Twilio Dialer installer (macOS / Linux)"
echo "=============================================="
echo
info "Module source: $MODULE_SRC"

[[ -f "$MODULE_SRC/__manifest__.py" ]] || fail "Module folder not found: $MODULE_SRC"
[[ -f "$REQ_FILE" ]] || fail "requirements.txt not found: $REQ_FILE"

# ── Step 1: locate Odoo / addons ─────────────────────────────────────────────
info "Step 1/4 — Looking for Odoo directories..."

CANDIDATES=()
while IFS= read -r path; do
  [[ -n "$path" ]] && CANDIDATES+=("$path")
done <<EOF
$HOME/odoo
$HOME/odoo18
$HOME/odoo-18
$HOME/src/odoo
$HOME/Documents/odoo
$HOME/Documents/odoo18
/opt/odoo
/opt/odoo18
/usr/lib/python3/dist-packages/odoo
EOF

# Also search shallow for odoo-bin / odoo.conf under home Documents
while IFS= read -r conf; do
  root="$(dirname "$conf")"
  CANDIDATES+=("$root")
done < <(find "$HOME/Documents" "$HOME" /opt /Applications -maxdepth 4 \
  \( -name 'odoo.conf' -o -name 'odoo-bin' \) 2>/dev/null | head -40)

# Deduplicate
UNIQUE=()
for c in "${CANDIDATES[@]}"; do
  [[ -d "$c" ]] || continue
  skip=0
  for u in "${UNIQUE[@]:-}"; do
    [[ "$u" == "$c" ]] && skip=1 && break
  done
  [[ $skip -eq 0 ]] && UNIQUE+=("$c")
done

ADDONS_DIR=""
ODOO_CONF=""
PYTHON_BIN=""

if ((${#UNIQUE[@]} > 0)); then
  echo
  echo "Found possible Odoo locations:"
  i=1
  for u in "${UNIQUE[@]}"; do
    echo "  [$i] $u"
    ((i++)) || true
  done
  echo "  [0] Enter path manually"
  echo
  read -r -p "Select number: " choice
  if [[ "$choice" == "0" || -z "$choice" ]]; then
    read -r -p "Enter Odoo root OR custom addons folder: " manual
    SELECTED="$manual"
  else
    SELECTED="${UNIQUE[$((choice-1))]:-}"
  fi
else
  warn "No Odoo folder auto-detected."
  read -r -p "Enter Odoo root OR custom addons folder: " SELECTED
fi

[[ -n "${SELECTED:-}" && -d "$SELECTED" ]] || fail "Invalid path: ${SELECTED:-}"

# Prefer a custom/extra addons folder under the selection
if [[ -d "$SELECTED/custom_addons" ]]; then
  ADDONS_DIR="$SELECTED/custom_addons"
elif [[ -d "$SELECTED/addons" && -f "$SELECTED/odoo-bin" ]]; then
  # Prefer custom next to community addons
  ADDONS_DIR="$SELECTED/custom_addons"
  mkdir -p "$ADDONS_DIR"
elif [[ -f "$SELECTED/__manifest__.py" ]]; then
  fail "You selected a single module folder. Select the parent addons directory instead."
elif [[ -d "$SELECTED" ]]; then
  # If user pointed at an addons dir that already contains modules, use it
  if compgen -G "$SELECTED/*/__manifest__.py" > /dev/null; then
    ADDONS_DIR="$SELECTED"
  else
    ADDONS_DIR="$SELECTED/custom_addons"
    mkdir -p "$ADDONS_DIR"
  fi
fi

ok "Install addons folder: $ADDONS_DIR"

# Find odoo.conf near selection
for conf in "$SELECTED/odoo.conf" "$SELECTED/debian/odoo.conf" "$HOME/.odoorc" "/etc/odoo/odoo.conf"; do
  if [[ -f "$conf" ]]; then
    ODOO_CONF="$conf"
    break
  fi
done

# ── Step 2: copy module ──────────────────────────────────────────────────────
info "Step 2/4 — Installing module into addons..."
TARGET="$ADDONS_DIR/twilio_dialer"

if [[ -e "$TARGET" ]]; then
  warn "Existing module found at $TARGET"
  read -r -p "Replace it? [y/N]: " repl
  if [[ "${repl:-N}" =~ ^[Yy]$ ]]; then
    rm -rf "$TARGET"
  else
    fail "Aborted (module already exists)."
  fi
fi

mkdir -p "$ADDONS_DIR"
cp -R "$MODULE_SRC" "$TARGET"
# Keep requirements next to module for reference
cp -f "$REQ_FILE" "$ADDONS_DIR/twilio_dialer_requirements.txt"
ok "Copied module → $TARGET"

# ── Step 3: update odoo.conf addons_path (optional) ──────────────────────────
info "Step 3/4 — Updating odoo.conf addons_path (optional)..."
if [[ -n "$ODOO_CONF" ]]; then
  echo "Found config: $ODOO_CONF"
  read -r -p "Add $ADDONS_DIR to addons_path in this file? [Y/n]: " upd
  if [[ ! "${upd:-Y}" =~ ^[Nn]$ ]]; then
    if grep -qE '^\s*addons_path\s*=' "$ODOO_CONF"; then
      if grep -qF "$ADDONS_DIR" "$ODOO_CONF"; then
        ok "addons_path already includes this folder"
      else
        # Append path to existing addons_path line
        python3 - "$ODOO_CONF" "$ADDONS_DIR" <<'PY'
import re, sys
conf, addon = sys.argv[1], sys.argv[2]
text = open(conf, encoding="utf-8").read()
def repl(m):
    val = m.group(1).strip()
    parts = [p.strip() for p in val.split(",") if p.strip()]
    if addon not in parts:
        parts.append(addon)
    return "addons_path = " + ",".join(parts)
new, n = re.subn(r"(?m)^\s*addons_path\s*=\s*(.*)$", repl, text, count=1)
if n:
    open(conf, "w", encoding="utf-8").write(new)
    print("updated")
else:
    print("no-change")
PY
        ok "Updated addons_path in $ODOO_CONF"
      fi
    else
      printf '\naddons_path = %s\n' "$ADDONS_DIR" >> "$ODOO_CONF"
      ok "Added addons_path to $ODOO_CONF"
    fi
  else
    warn "Skipped config update. Add this path manually:"
    echo "    $ADDONS_DIR"
  fi
else
  warn "No odoo.conf found. Add this to addons_path manually:"
  echo "    $ADDONS_DIR"
  echo "  Template: $REPO_ROOT/odoo.conf.example"
fi

# ── Step 4: install Python dependency ────────────────────────────────────────
info "Step 4/4 — Installing Python dependency (twilio)..."

for py in \
  "${ODOO_PYTHON:-}" \
  "$SELECTED/venv/bin/python" \
  "$SELECTED/.venv/bin/python" \
  "$(command -v python3 || true)" \
  "$(command -v python || true)"
do
  [[ -n "$py" && -x "$py" ]] || continue
  PYTHON_BIN="$py"
  break
done

[[ -n "$PYTHON_BIN" ]] || fail "Python not found. Install twilio manually: pip install -r requirements.txt"

echo "Using: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
read -r -p "Install requirements with this Python? [Y/n]: " do_pip
if [[ ! "${do_pip:-Y}" =~ ^[Nn]$ ]]; then
  "$PYTHON_BIN" -m pip install -r "$REQ_FILE"
  ok "Python packages installed"
else
  warn "Skipped pip. Later run:"
  echo "    $PYTHON_BIN -m pip install -r $REQ_FILE"
fi

echo
echo "=============================================="
echo "  Install complete"
echo "=============================================="
echo
echo "Next steps (use your EXISTING database + login):"
echo "  1. Restart Odoo"
echo "  2. Apps → Update Apps List"
echo "  3. Install \"Twilio Dialer\""
echo "  4. Open Twilio Dialer → Configuration and enter Account SID / Auth Token"
echo
echo "Module path: $TARGET"
echo
