#!/usr/bin/env bash
# Twilio Dialer — macOS / Linux installer
# Finds Odoo, extracts the corresponding tested version ZIP into custom addons, installs Python deps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_SRC="$SCRIPT_DIR/twilio_dialer"
REQ_FILE="$MODULE_SRC/requirements.txt"
[[ -f "$REQ_FILE" ]] || REQ_FILE="$SCRIPT_DIR/requirements.txt"

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

# ── Step 1: locate Odoo / addons ─────────────────────────────────────────────
info "Step 1/4 — Looking for Odoo directories..."

CANDIDATES=()
while IFS= read -r path; do
  [[ -n "$path" ]] && CANDIDATES+=("$path")
done <<EOF
$HOME/odoo
$HOME/odoo18
$HOME/odoo17
$HOME/odoo19
$HOME/odoo-18
$HOME/odoo-17
$HOME/odoo-19
$HOME/src/odoo
$HOME/Documents/odoo
$HOME/Documents/odoo18
$HOME/Documents/odoo17
$HOME/Documents/odoo19
/opt/odoo
/opt/odoo18
/opt/odoo17
/opt/odoo19
/usr/lib/python3/dist-packages/odoo
EOF

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

if [[ -d "$SELECTED/custom_addons" ]]; then
  ADDONS_DIR="$SELECTED/custom_addons"
elif [[ -d "$SELECTED/addons" && -f "$SELECTED/odoo-bin" ]]; then
  ADDONS_DIR="$SELECTED/custom_addons"
  mkdir -p "$ADDONS_DIR"
elif [[ -f "$SELECTED/__manifest__.py" ]]; then
  fail "You selected a single module folder. Select the parent addons directory instead."
elif [[ -d "$SELECTED" ]]; then
  if compgen -G "$SELECTED/*/__manifest__.py" > /dev/null; then
    ADDONS_DIR="$SELECTED"
  else
    ADDONS_DIR="$SELECTED/custom_addons"
    mkdir -p "$ADDONS_DIR"
  fi
fi

ok "Target custom addons folder: $ADDONS_DIR"

for conf in "$SELECTED/odoo.conf" "$SELECTED/debian/odoo.conf" "$HOME/.odoorc" "/etc/odoo/odoo.conf"; do
  if [[ -f "$conf" ]]; then
    ODOO_CONF="$conf"
    break
  fi
done

# ── Odoo Version Detection & ZIP Selection ────────────────────────────────────
ODOO_VERSION=""

if [[ -f "$SELECTED/odoo/release.py" ]]; then
  REL_TEXT="$(cat "$SELECTED/odoo/release.py" 2>/dev/null || true)"
elif [[ -f "$SELECTED/release.py" ]]; then
  REL_TEXT="$(cat "$SELECTED/release.py" 2>/dev/null || true)"
else
  REL_TEXT=""
fi

if [[ "$REL_TEXT" =~ version[[:space:]]*=[[:space:]]*[\'\"]([0-9]+\.[0-9]+) ]]; then
  VER="${BASH_REMATCH[1]}"
  if [[ "$VER" == 17* ]]; then ODOO_VERSION="17"; fi
  if [[ "$VER" == 18* ]]; then ODOO_VERSION="18"; fi
  if [[ "$VER" == 19* ]]; then ODOO_VERSION="19"; fi
fi

if [[ -z "$ODOO_VERSION" ]]; then
  if [[ "$SELECTED" == *17* ]]; then ODOO_VERSION="17"; fi
  if [[ "$SELECTED" == *19* ]]; then ODOO_VERSION="19"; fi
  if [[ "$SELECTED" == *18* ]]; then ODOO_VERSION="18"; fi
fi

if [[ -z "$ODOO_VERSION" ]]; then
  echo
  echo "Select your Odoo Version:"
  echo "  [1] Odoo 17"
  echo "  [2] Odoo 18"
  echo "  [3] Odoo 19"
  read -r -p "Select version [1-3]: " vchoice
  case "$vchoice" in
    1) ODOO_VERSION="17" ;;
    3) ODOO_VERSION="19" ;;
    *) ODOO_VERSION="18" ;;
  esac
fi

ok "Detected/Selected Odoo Version: Odoo $ODOO_VERSION"

ZIP_FILE=""
ZIP_CANDIDATES=()
if [[ "$ODOO_VERSION" == "17" ]]; then
  ZIP_CANDIDATES+=("$SCRIPT_DIR/twilio_dialer_17.0.zip" "$REPO_ROOT/twilio_dialer_17.0.zip")
elif [[ "$ODOO_VERSION" == "19" ]]; then
  ZIP_CANDIDATES+=("$SCRIPT_DIR/twilio_dialer_19.0.zip" "$REPO_ROOT/twilio_dialer_19.0.zip")
else
  ZIP_CANDIDATES+=("$SCRIPT_DIR/twilio_dialer.zip" "$SCRIPT_DIR/twilio_dialer_18.0.zip" "$REPO_ROOT/twilio_dialer.zip" "$REPO_ROOT/twilio_dialer_18.0.zip")
fi

for z in "${ZIP_CANDIDATES[@]}"; do
  if [[ -f "$z" ]]; then
    ZIP_FILE="$z"
    break
  fi
done

# ── Step 2: Extract module ───────────────────────────────────────────────────
info "Step 2/4 — Installing module into custom addons..."
TARGET="$ADDONS_DIR/twilio_dialer"

if [[ -e "$TARGET" ]]; then
  warn "Existing module found at $TARGET"
  read -r -p "Replace existing installation? [y/N]: " repl
  if [[ "${repl:-N}" =~ ^[Yy]$ ]]; then
    BACKUP_DIR="$ADDONS_DIR/twilio_dialer_backup_$(date +%Y%m%d%H%M%S)"
    info "Creating safety backup at $BACKUP_DIR..."
    mv "$TARGET" "$BACKUP_DIR"
  else
    fail "Aborted (existing module preserved)."
  fi
fi

mkdir -p "$ADDONS_DIR"

if [[ -n "$ZIP_FILE" && -f "$ZIP_FILE" ]]; then
  info "Extracting release ZIP: $ZIP_FILE → $ADDONS_DIR"
  unzip -q -o "$ZIP_FILE" -d "$ADDONS_DIR"

  # Handle double nesting if present
  if [[ -d "$TARGET/twilio_dialer" && -f "$TARGET/twilio_dialer/__manifest__.py" ]]; then
    info "Resolving nested directory structure..."
    mv "$TARGET/twilio_dialer" "$ADDONS_DIR/twilio_dialer_temp"
    rm -rf "$TARGET"
    mv "$ADDONS_DIR/twilio_dialer_temp" "$TARGET"
  fi
elif [[ -d "$MODULE_SRC" && -f "$MODULE_SRC/__manifest__.py" ]]; then
  info "Copying module source: $MODULE_SRC → $TARGET"
  cp -R "$MODULE_SRC" "$TARGET"
else
  fail "Could not find Twilio Dialer release ZIP or source folder for Odoo $ODOO_VERSION"
fi

# Critical Structure Check
[[ -f "$TARGET/__manifest__.py" ]] || fail "Verification Error: __manifest__.py not found at $TARGET/__manifest__.py"
[[ ! -f "$TARGET/twilio_dialer/__manifest__.py" ]] || fail "Verification Error: Double nesting detected at $TARGET/twilio_dialer/__manifest__.py"

ok "Module verified at $TARGET"

# ── Step 3: update odoo.conf addons_path (optional) ──────────────────────────
info "Step 3/4 — Updating odoo.conf addons_path (optional)..."
if [[ -n "$ODOO_CONF" ]]; then
  if grep -qE '/mnt/extra-addons' "$ODOO_CONF"; then
    ok "Docker odoo.conf already uses /mnt/extra-addons (host path not needed)"
  else
    echo "Found config: $ODOO_CONF"
    read -r -p "Add $ADDONS_DIR to addons_path in this file? [Y/n]: " upd
    if [[ ! "${upd:-Y}" =~ ^[Nn]$ ]]; then
      if grep -qE '^\s*addons_path\s*=' "$ODOO_CONF"; then
        if grep -qF "$ADDONS_DIR" "$ODOO_CONF"; then
          ok "addons_path already includes this folder"
        else
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
  fi
else
  warn "No odoo.conf found. Ensure $ADDONS_DIR is included in your addons_path."
fi

# ── Step 4: install Python dependency ────────────────────────────────────────
info "Step 4/4 — Installing Python dependencies (twilio, PyJWT)..."

if [[ -f "$SELECTED/docker-compose.yml" ]] && command -v docker >/dev/null 2>&1; then
  warn "Detected Docker Compose Odoo — installing twilio and PyJWT inside container."
  (
    cd "$SELECTED"
    export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-local-dev}"
    docker compose exec -u root -T odoo bash -lc \
      'pip3 install --break-system-packages twilio PyJWT 2>/dev/null || pip3 install twilio PyJWT'
  )
  ok "Python packages installed in Odoo container"
else
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

  if [[ -n "$PYTHON_BIN" ]]; then
    echo "Using: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
    read -r -p "Install requirements with this Python? [Y/n]: " do_pip
    if [[ ! "${do_pip:-Y}" =~ ^[Nn]$ ]]; then
      "$PYTHON_BIN" -m pip install twilio PyJWT
      ok "Python packages installed"
    fi
  else
    warn "Python environment not auto-detected. Ensure 'twilio' and 'PyJWT' packages are installed."
  fi
fi

# ── Customer Next-Steps Instructions ----------------------------------------
echo
echo "${GREEN}==========================================================${NC}"
echo "${GREEN}  Twilio Dialer has been installed into your Odoo Apps folder.${NC}"
echo "${GREEN}==========================================================${NC}"
echo
echo "${YELLOW}Next steps:${NC}"
echo "  1. Open Odoo."
echo "  2. Go to Settings."
echo "  3. Scroll down and activate Developer Mode."
echo "  4. Open Apps."
echo "  5. Search for \"Odoo Twilio Dialer\"."
echo "  6. Install the module."
echo "  7. Open Twilio Dialer and follow the setup wizard."
echo
echo "Diagnostic Info: Installed to $TARGET"
echo
