# Twilio Dialer - Windows installer (PowerShell)
# Finds Odoo, extracts the corresponding tested version ZIP into custom addons, installs Python deps.
# Run:
#   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Get-Item (Join-Path $ScriptDir "..")).FullName
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

# --- Step 1: locate Odoo / addons ---------------------------------------------
Write-Info "Step 1/4 - Looking for Odoo directories..."

$candidates = New-Object System.Collections.Generic.List[string]
$guesses = @(
    "$env:USERPROFILE\odoo",
    "$env:USERPROFILE\odoo18",
    "$env:USERPROFILE\odoo17",
    "$env:USERPROFILE\odoo19",
    "$env:USERPROFILE\Documents\odoo",
    "$env:USERPROFILE\Documents\odoo18",
    "$env:USERPROFILE\Documents\odoo17",
    "$env:USERPROFILE\Documents\odoo19",
    "C:\odoo",
    "C:\odoo18",
    "C:\odoo17",
    "C:\odoo19",
    "C:\Program Files\Odoo",
    'C:\Program Files (x86)\Odoo',
    "D:\odoo",
    "D:\odoo18",
    "D:\odoo17",
    "D:\odoo19"
)

foreach ($g in $guesses) {
    if (Test-Path -LiteralPath $g) { [void]$candidates.Add($g) }
}

# Shallow search for odoo-bin / odoo.conf
$searchRoots = @("$env:USERPROFILE\Documents", "$env:USERPROFILE", "C:\Odoo", "D:\Odoo", "C:\Program Files\Odoo", 'C:\Program Files (x86)\Odoo')
foreach ($root in $searchRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    try {
        Get-ChildItem -LiteralPath $root -Recurse -Depth 3 -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -in @("odoo-bin", "odoo.conf", "odoo-bin.exe") } |
            Select-Object -First 30 |
            ForEach-Object { [void]$candidates.Add($_.Directory.FullName) }
    } catch {}
}

$unique = @($candidates | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ })

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

# Normalize user input: ensure it's a string and strip surrounding quotes/spaces
$selected = [string]$selected
$selected = $selected.Trim('"').Trim()

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
    $hasModules = @(Get-ChildItem -Path $selected -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "__manifest__.py") })
    if ($hasModules.Count -gt 0) {
        $addonsDir = $selected
    } else {
        $addonsDir = $custom
        New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null
    }
}

if (-not $addonsDir) {
    $msg = ('Internal error: addons directory not determined. Selected="{0}"; custom="{1}"; addons="{2}"; odooBin="{3}"' -f $selected, $custom, $addons, $odooBin)
    Fail $msg
}

Write-Ok "Target custom addons folder: $addonsDir"

$odooConf = $null
foreach ($conf in @(
    (Join-Path $selected "odoo.conf"),
    (Join-Path $selected "debian\odoo.conf"),
    "$env:USERPROFILE\.odoorc",
    "C:\Program Files\Odoo\odoo.conf"
)) {
    if (Test-Path $conf) { $odooConf = $conf; break }
}

# --- Version Detection & ZIP Selection ----------------------------------------
$odooVersion = $null

$releasePy = Join-Path $selected "odoo\release.py"
if (-not (Test-Path $releasePy)) {
    $releasePy = Join-Path $selected "release.py"
}
if (Test-Path $releasePy) {
    $relText = Get-Content -Raw -Path $releasePy -ErrorAction SilentlyContinue
    if ($relText -match 'version\s*=\s*[''"](\d+\.\d+)') {
        $v = $matches[1]
        if ($v.StartsWith("17")) { $odooVersion = "17" }
        elseif ($v.StartsWith("18")) { $odooVersion = "18" }
        elseif ($v.StartsWith("19")) { $odooVersion = "19" }
    }
}

if (-not $odooVersion) {
    if ($selected -match "17") { $odooVersion = "17" }
    elseif ($selected -match "19") { $odooVersion = "19" }
    elseif ($selected -match "18") { $odooVersion = "18" }
}

if (-not $odooVersion) {
    Write-Host ""
    Write-Host "Select your Odoo Version:"
    Write-Host "  [1] Odoo 17"
    Write-Host "  [2] Odoo 18"
    Write-Host "  [3] Odoo 19"
    $vChoice = Read-Host "Select version [1-3]"
    switch ($vChoice) {
        "1" { $odooVersion = "17" }
        "3" { $odooVersion = "19" }
        default { $odooVersion = "18" }
    }
}

Write-Ok "Detected/Selected Odoo Version: Odoo $odooVersion"

$zipFile = $null
$zipCandidates = @()

if ($odooVersion -eq "17") {
    $zipCandidates += (Join-Path $ScriptDir "twilio_dialer_17.0.zip")
    $zipCandidates += (Join-Path $RepoRoot "twilio_dialer_17.0.zip")
    $zipCandidates += "D:\Odoo\custom_addons\twilio_dialer_17.0.zip"
} elseif ($odooVersion -eq "19") {
    $zipCandidates += (Join-Path $ScriptDir "twilio_dialer_19.0.zip")
    $zipCandidates += (Join-Path $RepoRoot "twilio_dialer_19.0.zip")
    $zipCandidates += "D:\Odoo\custom_addons\twilio_dialer_19.0.zip"
} else {
    $zipCandidates += (Join-Path $ScriptDir "twilio_dialer.zip")
    $zipCandidates += (Join-Path $ScriptDir "twilio_dialer_18.0.zip")
    $zipCandidates += (Join-Path $RepoRoot "twilio_dialer.zip")
    $zipCandidates += (Join-Path $RepoRoot "twilio_dialer_18.0.zip")
    $zipCandidates += "D:\Odoo\custom_addons\twilio_dialer.zip"
}

foreach ($zc in $zipCandidates) {
    if (Test-Path $zc) {
        $zipFile = $zc
        break
    }
}

# --- Step 2: Extract module into custom addons --------------------------------
Write-Info "Step 2/4 - Installing module into custom addons..."
$target = Join-Path $addonsDir "twilio_dialer"

if (Test-Path $target) {
    Write-Note "Existing module found at $target"
    $repl = Read-Host "Replace existing installation? [y/N]"
    if ($repl -match '^[Yy]$') {
        $backupDir = Join-Path $addonsDir ("twilio_dialer_backup_" + (Get-Date -Format "yyyyMMddHHmmss"))
        Write-Info "Creating safety backup at $backupDir..."
        Move-Item -Path $target -Destination $backupDir -Force
    } else {
        Fail "Aborted (existing module preserved)."
    }
}

New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null

if ($zipFile -and (Test-Path $zipFile)) {
    Write-Info "Extracting release ZIP: $zipFile -> $addonsDir"
    Expand-Archive -Path $zipFile -DestinationPath $addonsDir -Force

    # Resolve double nesting if present
    $nestedTarget = Join-Path $target "twilio_dialer"
    if ((Test-Path $nestedTarget) -and (Test-Path (Join-Path $nestedTarget "__manifest__.py"))) {
        Write-Info "Resolving nested directory structure..."
        $tempMove = Join-Path $addonsDir "twilio_dialer_temp"
        Move-Item -Path $nestedTarget -Destination $tempMove -Force
        Remove-Item -Path $target -Recurse -Force
        Move-Item -Path $tempMove -Destination $target -Force
    }
} elseif (Test-Path (Join-Path $ModuleSrc "__manifest__.py")) {
    Write-Info "Extracting/Copying module source: $ModuleSrc -> $target"
    Copy-Item -Recurse -Force $ModuleSrc $target
} else {
    Fail "Could not find Twilio Dialer release ZIP or source folder for Odoo $odooVersion"
}

# Critical Structure Check
$manifestPath = Join-Path $target "__manifest__.py"
if (-not (Test-Path $manifestPath)) {
    Fail "Verification Error: __manifest__.py not found at $manifestPath"
}
$nestedManifest = Join-Path $target "twilio_dialer\__manifest__.py"
if (Test-Path $nestedManifest) {
    Fail "Verification Error: Double nesting detected at $nestedManifest"
}

Write-Ok "Module verified at $target"

# --- Step 3: update odoo.conf addons_path (optional) --------------------------
Write-Info "Step 3/4 - Updating odoo.conf addons_path (optional)..."
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
    Write-Note "No odoo.conf found. Ensure $addonsDir is included in your addons_path."
}

# --- Step 4: install Python dependency (twilio & PyJWT) -----------------------
Write-Info "Step 4/4 - Installing Python dependencies..."

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

if ($pythonBin) {
    Write-Host "Using Python: $pythonBin"
    $doPip = Read-Host "Install dependencies (twilio, PyJWT) with this Python? [Y/n]"
    if ($doPip -notmatch '^[Nn]$') {
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $pythonBin -m pip install --quiet twilio PyJWT
            Write-Ok "Python packages installed"
        } catch {
            Write-Note "Pip completed."
        } finally {
            $ErrorActionPreference = $oldEAP
        }
    }
} else {
    Write-Note "Python environment not auto-detected. Ensure 'twilio' and 'PyJWT' packages are installed."
}

# --- Customer Next-Steps Instructions ----------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Twilio Dialer has been installed into your Odoo Apps folder." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open Odoo."
Write-Host "  2. Go to Settings."
Write-Host "  3. Scroll down and activate Developer Mode."
Write-Host "  4. Open Apps."
Write-Host "  5. Search for `"Odoo Twilio Dialer`"."
Write-Host "  6. Install the module."
Write-Host "  7. Open Twilio Dialer and follow the setup wizard."
Write-Host ""
Write-Host "Diagnostic Info: Installed to $target" -ForegroundColor Gray
Write-Host ""