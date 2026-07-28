# Twilio Dialer — Windows installer (PowerShell)
# Finds Odoo, copies the module into custom addons, installs Python deps.
# Run:
#   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..")
$ModuleSrc = Join-Path $RepoRoot "twilio_dialer"
$ReqFile   = Join-Path $RepoRoot "requirements.txt"

function Write-Info($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "OK: $msg" -ForegroundColor Green }
function Write-Note($msg)  { Write-Host "NOTE: $msg" -ForegroundColor Yellow }
function Fail($msg)        { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=============================================="
Write-Host "  Twilio Dialer installer (Windows)"
Write-Host "=============================================="
Write-Host ""
Write-Info "Module source: $ModuleSrc"

if (-not (Test-Path (Join-Path $ModuleSrc "__manifest__.py"))) {
    Fail "Module folder not found: $ModuleSrc"
}
if (-not (Test-Path $ReqFile)) {
    Fail "requirements.txt not found: $ReqFile"
}

# ── Step 1: locate Odoo / addons ─────────────────────────────────────────────
Write-Info "Step 1/4 — Looking for Odoo directories..."

$candidates = New-Object System.Collections.Generic.List[string]
$guesses = @(
    "$env:USERPROFILE\odoo",
    "$env:USERPROFILE\odoo18",
    "$env:USERPROFILE\Documents\odoo",
    "$env:USERPROFILE\Documents\odoo18",
    "C:\odoo",
    "C:\odoo18",
    "C:\Program Files\Odoo",
    "C:\Program Files (x86)\Odoo",
    "D:\odoo",
    "D:\odoo18"
)

foreach ($g in $guesses) {
    if (Test-Path $g) { [void]$candidates.Add($g) }
}

# Shallow search for odoo-bin / odoo.conf
$searchRoots = @("$env:USERPROFILE\Documents", "$env:USERPROFILE", "C:\")
foreach ($root in $searchRoots) {
    if (-not (Test-Path $root)) { continue }
    try {
        Get-ChildItem -Path $root -Recurse -Depth 3 -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -in @("odoo-bin", "odoo.conf", "odoo-bin.exe") } |
            Select-Object -First 30 |
            ForEach-Object { [void]$candidates.Add($_.Directory.FullName) }
    } catch {}
}

$unique = @($candidates | Select-Object -Unique | Where-Object { Test-Path $_ })

$selected = $null
if ($unique.Count -gt 0) {
    Write-Host ""
    Write-Host "Found possible Odoo locations:"
    for ($i = 0; $i -lt $unique.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $unique[$i])
    }
    Write-Host "  [0] Enter path manually"
    Write-Host ""
    $choice = Read-Host "Select number"
    if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
        $selected = Read-Host "Enter Odoo root OR custom addons folder"
    } else {
        $idx = [int]$choice - 1
        if ($idx -lt 0 -or $idx -ge $unique.Count) { Fail "Invalid selection" }
        $selected = $unique[$idx]
    }
} else {
    Write-Note "No Odoo folder auto-detected."
    $selected = Read-Host "Enter Odoo root OR custom addons folder"
}

if ([string]::IsNullOrWhiteSpace($selected) -or -not (Test-Path $selected)) {
    Fail "Invalid path: $selected"
}

$addonsDir = $null
$custom = Join-Path $selected "custom_addons"
$addons = Join-Path $selected "addons"
$odooBin = Join-Path $selected "odoo-bin"

if (Test-Path $custom) {
    $addonsDir = $custom
} elseif ((Test-Path $addons) -and (Test-Path $odooBin)) {
    $addonsDir = $custom
    New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null
} else {
    $hasModules = Get-ChildItem -Path $selected -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "__manifest__.py") }
    if ($hasModules) {
        $addonsDir = $selected
    } else {
        $addonsDir = $custom
        New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null
    }
}

Write-Ok "Install addons folder: $addonsDir"

$odooConf = $null
foreach ($conf in @(
    (Join-Path $selected "odoo.conf"),
    (Join-Path $selected "debian\odoo.conf"),
    "$env:USERPROFILE\.odoorc",
    "C:\Program Files\Odoo\odoo.conf"
)) {
    if (Test-Path $conf) { $odooConf = $conf; break }
}

# ── Step 2: copy module ──────────────────────────────────────────────────────
Write-Info "Step 2/4 — Installing module into addons..."
$target = Join-Path $addonsDir "twilio_dialer"

if (Test-Path $target) {
    Write-Note "Existing module found at $target"
    $repl = Read-Host "Replace it? [y/N]"
    if ($repl -match '^[Yy]$') {
        Remove-Item -Recurse -Force $target
    } else {
        Fail "Aborted (module already exists)."
    }
}

New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null
Copy-Item -Recurse -Force $ModuleSrc $target
Copy-Item -Force $ReqFile (Join-Path $addonsDir "twilio_dialer_requirements.txt")
Write-Ok "Copied module → $target"

# ── Step 3: update odoo.conf addons_path (optional) ──────────────────────────
Write-Info "Step 3/4 — Updating odoo.conf addons_path (optional)..."
if ($odooConf) {
    Write-Host "Found config: $odooConf"
    $upd = Read-Host "Add $addonsDir to addons_path in this file? [Y/n]"
    if ($upd -notmatch '^[Nn]$') {
        $text = Get-Content -Raw -Path $odooConf
        if ($text -match '(?m)^\s*addons_path\s*=\s*(.*)$') {
            if ($text -like "*$addonsDir*") {
                Write-Ok "addons_path already includes this folder"
            } else {
                $text = [regex]::Replace(
                    $text,
                    '(?m)^\s*addons_path\s*=\s*(.*)$',
                    {
                        param($m)
                        $parts = @($m.Groups[1].Value.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
                        if ($parts -notcontains $addonsDir) { $parts += $addonsDir }
                        return "addons_path = " + ($parts -join ",")
                    },
                    1
                )
                Set-Content -Path $odooConf -Value $text -NoNewline
                Write-Ok "Updated addons_path in $odooConf"
            }
        } else {
            Add-Content -Path $odooConf -Value "`r`naddons_path = $addonsDir"
            Write-Ok "Added addons_path to $odooConf"
        }
    } else {
        Write-Note "Skipped config update. Add this path manually:"
        Write-Host "    $addonsDir"
    }
} else {
    Write-Note "No odoo.conf found. Add this to addons_path manually:"
    Write-Host "    $addonsDir"
    Write-Host "  Template: $(Join-Path $RepoRoot 'odoo.conf.example')"
}

# ── Step 4: install Python dependency ────────────────────────────────────────
Write-Info "Step 4/4 — Installing Python dependency (twilio)..."

# Normalize requirements to UTF-8 (pip fails on UTF-16)
$reqUtf8 = Join-Path $env:TEMP "twilio_dialer_requirements_utf8.txt"
$raw = [System.IO.File]::ReadAllBytes($ReqFile)
$text = $null
if (($raw.Length -ge 2) -and (($raw[0] -eq 0xFF -and $raw[1] -eq 0xFE) -or ($raw[0] -eq 0xFE -and $raw[1] -eq 0xFF) -or ($raw.Length -gt 3 -and $raw[1] -eq 0x00))) {
    $text = [System.Text.Encoding]::Unicode.GetString($raw)
} else {
    $text = [System.Text.Encoding]::UTF8.GetString($raw)
}
$reqLines = @()
foreach ($line in ($text -split "`r?`n")) {
    $s = $line.Trim()
    if (-not [string]::IsNullOrWhiteSpace($s) -and -not $s.StartsWith("#")) {
        $reqLines += $s
    }
}
[System.IO.File]::WriteAllText($reqUtf8, (($reqLines -join "`n") + "`n"), [System.Text.UTF8Encoding]::new($false))

$pythonCandidates = @(
    $env:ODOO_PYTHON,
    (Join-Path $selected "venv\Scripts\python.exe"),
    (Join-Path $selected ".venv\Scripts\python.exe"),
    (Join-Path $selected "python\python.exe"),
    "python",
    "py"
) | Where-Object { $_ }

$pythonBin = $null
foreach ($py in $pythonCandidates) {
    try {
        if ($py -eq "python" -or $py -eq "py") {
            $null = & $py --version 2>$null
            if ($LASTEXITCODE -eq 0) { $pythonBin = $py; break }
        } elseif (Test-Path $py) {
            $pythonBin = $py
            break
        }
    } catch {}
}

if (-not $pythonBin) {
    Fail "Python not found. Install twilio manually: pip install -r requirements.txt"
}

Write-Host "Using: $pythonBin"
& $pythonBin --version
$doPip = Read-Host "Install requirements with this Python? [Y/n]"
if ($doPip -notmatch '^[Nn]$') {
    & $pythonBin -m pip install -r $reqUtf8
    Write-Ok "Python packages installed"
} else {
    Write-Note "Skipped pip. Later run:"
    Write-Host "    $pythonBin -m pip install -r $ReqFile"
}
Remove-Item -Force $reqUtf8 -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=============================================="
Write-Host "  Install complete"
Write-Host "=============================================="
Write-Host ""
Write-Host "Next steps (use your EXISTING database + login):"
Write-Host "  1. Restart Odoo"
Write-Host "  2. Apps → Update Apps List"
Write-Host "  3. Install ""Twilio Dialer"""
Write-Host "  4. Open Twilio Dialer → Configuration and enter Account SID / Auth Token"
Write-Host ""
Write-Host "Module path: $target"
Write-Host ""
