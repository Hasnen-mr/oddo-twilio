# MCP Claude Integration for Odoo - Windows Installer (PowerShell)
# Finds Odoo, extracts the corresponding version package into custom addons, updates config & dependencies.
# Run:
#   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1

param(
    [string]$OdooPath = $null,
    [string]$OdooVersion = $null,
    [switch]$NonInteractive = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $ScriptDir "..\__manifest__.py")) {
    $ModuleSrc = (Get-Item (Join-Path $ScriptDir "..")).FullName
    $RepoRoot  = (Get-Item (Join-Path $ScriptDir "..\..")).FullName
} else {
    $RepoRoot  = (Get-Item (Join-Path $ScriptDir "..")).FullName
    $ModuleSrc = Join-Path $RepoRoot "mcp_claude"
}

function Write-Info($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "OK: $msg" -ForegroundColor Green }
function Write-Note($msg)  { Write-Host "NOTE: $msg" -ForegroundColor Yellow }
function Fail($msg)        { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  MCP Claude Integration Installer (Windows)"  -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: locate Odoo / addons ---------------------------------------------
Write-Info "Step 1/4 - Looking for Odoo installation directories across drives..."

$selected = $null
if ($OdooPath) {
    $selected = $OdooPath
} else {
    $candidates = New-Object System.Collections.Generic.List[string]

    $userGuesses = @(
        "$env:USERPROFILE\odoo",
        "$env:USERPROFILE\odoo18",
        "$env:USERPROFILE\odoo17",
        "$env:USERPROFILE\odoo19",
        "$env:USERPROFILE\Documents\odoo",
        "$env:USERPROFILE\Documents\odoo18",
        "$env:USERPROFILE\Documents\odoo17",
        "$env:USERPROFILE\Documents\odoo19"
    )
    foreach ($g in $userGuesses) {
        if (Test-Path -LiteralPath $g) { [void]$candidates.Add($g) }
    }

    $systemDrives = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Root
    foreach ($driveRoot in $systemDrives) {
        if (-not (Test-Path -LiteralPath $driveRoot)) { continue }

        $driveGuesses = @(
            (Join-Path $driveRoot "odoo"),
            (Join-Path $driveRoot "odoo17"),
            (Join-Path $driveRoot "odoo18"),
            (Join-Path $driveRoot "odoo19"),
            (Join-Path $driveRoot "odoo-17"),
            (Join-Path $driveRoot "odoo-18"),
            (Join-Path $driveRoot "odoo-19"),
            (Join-Path $driveRoot "Program Files\Odoo"),
            (Join-Path $driveRoot "Program Files (x86)\Odoo"),
            (Join-Path $driveRoot "src\odoo"),
            (Join-Path $driveRoot "custom_addons")
        )
        foreach ($dg in $driveGuesses) {
            if (Test-Path -LiteralPath $dg) { [void]$candidates.Add($dg) }
        }

        try {
            Get-ChildItem -LiteralPath $driveRoot -Recurse -Depth 3 -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -in @("odoo-bin", "odoo.conf", "odoo-bin.exe") } |
                Select-Object -First 20 |
                ForEach-Object { [void]$candidates.Add($_.Directory.FullName) }
        } catch {}
    }

    $unique = @($candidates | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ })

    if ($unique.Count -gt 0) {
        Write-Host ""
        Write-Host "Found possible Odoo locations across your system:"
        for ($i = 0; $i -lt $unique.Count; $i++) {
            Write-Host ("  [{0}] {1}" -f ($i + 1), $unique[$i])
        }
        Write-Host "  [0] Enter custom path manually"
        Write-Host ""
        $choice = Read-Host "Select number [0-$($unique.Count)]"
        if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
            $selected = Read-Host "Enter Odoo root OR custom addons folder path (e.g. C:\Odoo or D:\custom_addons)"
        } else {
            $idx = [int]$choice - 1
            if ($idx -lt 0 -or $idx -ge $unique.Count) { Fail "Invalid selection" }
            $selected = $unique[$idx]
        }
    } else {
        Write-Note "No Odoo folder auto-detected across connected drives."
        $selected = Read-Host "Enter Odoo root OR custom addons folder path (e.g. C:\Odoo or D:\custom_addons)"
    }
}

$selected = [string]$selected
$selected = $selected.Trim('"').Trim().TrimEnd('\').TrimEnd('/')

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
    Fail "addons directory could not be determined for: $selected"
}

Write-Ok "Target custom addons folder: $addonsDir"

$odooConf = $null
$confGuesses = @(
    (Join-Path $selected "odoo.conf"),
    (Join-Path $selected "odoo19.conf"),
    (Join-Path $selected "odoo18.conf"),
    (Join-Path $selected "odoo17.conf"),
    (Join-Path $selected "debian\odoo.conf"),
    (Join-Path (Split-Path -Parent $selected) "odoo.conf"),
    "$env:USERPROFILE\.odoorc",
    "C:\Program Files\Odoo\odoo.conf",
    "C:\Program Files (x86)\Odoo\odoo.conf"
)

foreach ($conf in $confGuesses) {
    if ($conf -and (Test-Path -LiteralPath $conf)) { $odooConf = $conf; break }
}

# --- Version Detection & ZIP Selection ----------------------------------------
$detectedVersion = $null
if ($OdooVersion) {
    $detectedVersion = $OdooVersion
} else {
    $releasePy = Join-Path $selected "odoo\release.py"
    if (-not (Test-Path $releasePy)) {
        $releasePy = Join-Path $selected "release.py"
    }
    if (Test-Path $releasePy) {
        $relText = Get-Content -Raw -Path $releasePy -ErrorAction SilentlyContinue
        if ($relText -match 'version\s*=\s*[''"](\d+\.\d+)') {
            $v = $matches[1]
            if ($v.StartsWith("17")) { $detectedVersion = "17" }
            elseif ($v.StartsWith("18")) { $detectedVersion = "18" }
            elseif ($v.StartsWith("19")) { $detectedVersion = "19" }
        }
    }

    if (-not $detectedVersion) {
        if ($selected -match "17") { $detectedVersion = "17" }
        elseif ($selected -match "19") { $detectedVersion = "19" }
        elseif ($selected -match "18") { $detectedVersion = "18" }
    }

    if (-not $detectedVersion) {
        if ($NonInteractive) {
            $detectedVersion = "18"
        } else {
            Write-Host ""
            Write-Host "Select your Odoo Version:"
            Write-Host "  [1] Odoo 17"
            Write-Host "  [2] Odoo 18"
            Write-Host "  [3] Odoo 19"
            $vChoice = Read-Host "Select version [1-3]"
            switch ($vChoice) {
                "1" { $detectedVersion = "17" }
                "3" { $detectedVersion = "19" }
                default { $detectedVersion = "18" }
            }
        }
    }
}

Write-Ok "Target Odoo Version: Odoo $detectedVersion"

$zipFile = $null
$zipCandidates = @(
    (Join-Path $ScriptDir "..\packages\mcp_claude_$($detectedVersion).0.zip"),
    (Join-Path $ScriptDir "packages\mcp_claude_$($detectedVersion).0.zip"),
    (Join-Path $ScriptDir "mcp_claude_$($detectedVersion).0.zip"),
    (Join-Path $RepoRoot "release\packages\mcp_claude_$($detectedVersion).0.zip"),
    (Join-Path $RepoRoot "packages\mcp_claude_$($detectedVersion).0.zip"),
    (Join-Path $RepoRoot "mcp_claude_$($detectedVersion).0.zip")
)

foreach ($zc in $zipCandidates) {
    if ($zc -and (Test-Path -LiteralPath $zc)) {
        $zipFile = $zc
        break
    }
}

# --- Step 2: Extract module into custom addons --------------------------------
Write-Info "Step 2/4 - Installing MCP Claude module into custom addons..."
$target = Join-Path $addonsDir "mcp_claude"

if (Test-Path $target) {
    Write-Note "Existing module found at $target [UPGRADE MODE]"
    if ($NonInteractive) {
        $repl = "Y"
    } else {
        $repl = Read-Host "Replace existing installation and perform upgrade? [Y/n]"
    }
    if ($repl -notmatch '^[Nn]$') {
        $backupDir = Join-Path $addonsDir ("mcp_claude_backup_" + (Get-Date -Format "yyyyMMddHHmmss"))
        Write-Info "Creating safety backup at $backupDir..."
        Move-Item -Path $target -Destination $backupDir -Force
    } else {
        Fail "Installation aborted. Existing module preserved."
    }
} else {
    Write-Info "Performing NEW INSTALLATION..."
}

New-Item -ItemType Directory -Force -Path $addonsDir | Out-Null

if ($zipFile -and (Test-Path $zipFile)) {
    Write-Info "Extracting release package: $zipFile -> $addonsDir"
    Expand-Archive -Path $zipFile -DestinationPath $addonsDir -Force

    $nestedTarget = Join-Path $target "mcp_claude"
    if ((Test-Path $nestedTarget) -and (Test-Path (Join-Path $nestedTarget "__manifest__.py"))) {
        Write-Info "Resolving nested directory structure..."
        $tempMove = Join-Path $addonsDir "mcp_claude_temp"
        Move-Item -Path $nestedTarget -Destination $tempMove -Force
        Remove-Item -Path $target -Recurse -Force
        Move-Item -Path $tempMove -Destination $target -Force
    }
} elseif (Test-Path (Join-Path $ModuleSrc "__manifest__.py")) {
    Write-Info "Copying module source: $ModuleSrc -> $target"
    Copy-Item -Recurse -Force $ModuleSrc $target
} else {
    Fail "Could not find MCP Claude release package for Odoo $detectedVersion"
}

# Verification Check
$manifestPath = Join-Path $target "__manifest__.py"
if (-not (Test-Path $manifestPath)) {
    Fail "Verification Error: __manifest__.py not found at $manifestPath"
}
$nestedManifest = Join-Path $target "mcp_claude\__manifest__.py"
if (Test-Path $nestedManifest) {
    Fail "Verification Error: Double nesting detected at $nestedManifest"
}

Write-Ok "Module verified at $target"

# --- Step 3: update odoo.conf addons_path (optional) --------------------------
Write-Info "Step 3/4 - Registering custom addons in odoo.conf (addons_path)..."

if (-not $odooConf -and -not $NonInteractive) {
    Write-Note "No odoo.conf auto-detected in $selected."
    $manualConf = Read-Host "Enter full path to your odoo.conf file (or press Enter to skip)"
    $manualConf = [string]$manualConf
    $manualConf = $manualConf.Trim('"').Trim()
    if (-not [string]::IsNullOrWhiteSpace($manualConf) -and (Test-Path $manualConf)) {
        $odooConf = $manualConf
    }
}

if ($odooConf) {
    Write-Host "Found config file: $odooConf"
    if ($NonInteractive) {
        $upd = "Y"
    } else {
        $upd = Read-Host "Add $addonsDir to addons_path in $odooConf? [Y/n]"
    }
    if ($upd -notmatch '^[Nn]$') {
        $text = Get-Content -Raw -Path $odooConf
        $normAddonsDir = $addonsDir.Replace("/", "\").TrimEnd("\")

        if ($text -match '(?m)^\s*addons_path\s*=\s*(.*)$') {
            $existingPathVal = $Matches[1].Trim()
            $existingParts = @($existingPathVal.Split(",") | ForEach-Object { $_.Trim().Replace("/", "\").TrimEnd("\") } | Where-Object { $_ })

            if ($existingParts -contains $normAddonsDir) {
                Write-Ok "addons_path in $odooConf already includes $addonsDir"
            } else {
                $newAddonsPathVal = $existingPathVal + "," + $addonsDir
                $text = [regex]::Replace(
                    $text,
                    '(?m)^\s*addons_path\s*=\s*(.*)$',
                    "addons_path = $newAddonsPathVal",
                    1
                )
                Set-Content -Path $odooConf -Value $text -NoNewline
                Write-Ok "Updated addons_path in $odooConf successfully!"
            }
        } else {
            if ($text -match '(?m)^\[options\]') {
                $text = [regex]::Replace($text, '(?m)^\[options\]', "[options]`r`naddons_path = $addonsDir", 1)
            } else {
                $text = "`r`naddons_path = $addonsDir`r`n" + $text
            }
            Set-Content -Path $odooConf -Value $text -NoNewline
            Write-Ok "Added addons_path = $addonsDir to $odooConf"
        }
    } else {
        Write-Note "Skipped config update. Ensure $addonsDir is added to addons_path manually."
    }
} else {
    Write-Note "No odoo.conf file specified. Ensure $addonsDir is included in your addons_path manually."
}

# --- Step 4: install Python dependencies --------------------------------------
Write-Info "Step 4/4 - Installing Python dependencies (PyJWT, requests, cryptography, jsonschema)..."

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
    if ($NonInteractive) {
        $doPip = "Y"
    } else {
        $doPip = Read-Host "Install required Python dependencies (PyJWT, requests, cryptography, jsonschema)? [Y/n]"
    }
    if ($doPip -notmatch '^[Nn]$') {
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $pythonBin -m pip install --quiet PyJWT requests cryptography jsonschema
            Write-Ok "Python packages installed successfully!"
        } catch {
            Write-Note "Pip execution completed."
        } finally {
            $ErrorActionPreference = $oldEAP
        }
    }
} else {
    Write-Note "Python environment not auto-detected. Ensure 'PyJWT', 'requests', and 'cryptography' are installed."
}

# --- Customer Next-Steps Instructions ----------------------------------------
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  MCP Claude Integration has been installed into Odoo Apps." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart your Odoo server."
Write-Host "  2. Open Odoo in your web browser."
Write-Host "  3. Go to Settings -> Activate Developer Mode."
Write-Host "  4. Open Apps menu."
Write-Host "  5. Click `"Update Apps List`" in the top navigation bar."
Write-Host "  6. Search for `"MCP Claude`"."
Write-Host "  7. Click `"Activate`" (or Install) to enable the module."
Write-Host "  8. Open MCP Claude -> Control Center to configure your API keys."
Write-Host ""
Write-Host "Diagnostic Info: Installed to $target" -ForegroundColor Gray
Write-Host ""
