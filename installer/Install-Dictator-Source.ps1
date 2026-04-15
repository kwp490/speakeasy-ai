<#
.SYNOPSIS
    Install dictat0r.AI from source (developer/contributor path).

.DESCRIPTION
    Copies the local dictat0r.AI source tree to the install directory, installs
    Python 3.11 and uv via winget, syncs all dependencies, downloads model
    weights for both engines, and creates a desktop shortcut.

    Requires Administrator elevation. Installs everything to C:\Program Files\dictat0r.AI\
    (binaries, models, config, logs, temp).

.NOTES
    Run in an elevated PowerShell session from within the repo:
        Set-ExecutionPolicy Bypass -Scope Process -Force
        .\installer\Install-Dictator-Source.ps1
#>

#Requires -RunAsAdministrator
#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$InstallDir = "C:\Program Files\dictat0r.AI"
$ModelsDir = "$InstallDir\models"
$ConfigDir = "$InstallDir\config"
$LogsDir   = "$InstallDir\logs"
$TempDir   = "$InstallDir\temp"
$RepoName = Split-Path -Leaf $PWD.Path

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Already($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor DarkGray }
function Write-Ok($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

function Invoke-NativeCommand {
    <# Run a native command, print indented output, and throw on failure. #>
    param([string]$Label, [scriptblock]$Command)
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Command 2>&1
        foreach ($line in $output) { Write-Host "  $line" }
    } finally {
        $ErrorActionPreference = $prevPref
    }
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit code $LASTEXITCODE)" }
}

function Invoke-StreamingCommand {
    <# Run a native command, streaming output line-by-line for real-time progress. #>
    param([string]$Label, [scriptblock]$Command)
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Command 2>&1 | ForEach-Object { Write-Host "  $_" }
    } finally {
        $ErrorActionPreference = $prevPref
    }
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit code $LASTEXITCODE)" }
}

function Update-OutdatedFiles {
    <# Compare every file in SourceDir against DestDir; force-copy any that
       are missing or older in the destination.  Returns the count of files updated. #>
    param(
        [Parameter(Mandatory)] [string]$SourceDir,
        [Parameter(Mandatory)] [string]$DestDir,
        [string[]]$ExcludeDirs = @('.git', '__pycache__', '.venv'),
        [string[]]$ExcludeExts = @('.pyc')
    )

    $updated = 0
    $srcItems = Get-ChildItem -Path $SourceDir -File -Recurse -Force
    foreach ($srcFile in $srcItems) {
        $rel = $srcFile.FullName.Substring($SourceDir.TrimEnd('\').Length + 1)

        $skip = $false
        foreach ($exDir in $ExcludeDirs) {
            if ($rel -like "$exDir\*" -or $rel -like "*\$exDir\*") { $skip = $true; break }
        }
        if ($skip) { continue }

        foreach ($exExt in $ExcludeExts) {
            if ($srcFile.Extension -eq $exExt) { $skip = $true; break }
        }
        if ($skip) { continue }

        $destFile = Join-Path $DestDir $rel
        if (-not (Test-Path $destFile)) {
            $destParent = Split-Path $destFile -Parent
            if (-not (Test-Path $destParent)) {
                New-Item -ItemType Directory -Path $destParent -Force | Out-Null
            }
            Copy-Item -Path $srcFile.FullName -Destination $destFile -Force
            Write-Host "  [NEW]  $rel" -ForegroundColor Yellow
            $updated++
        } elseif ($srcFile.LastWriteTimeUtc -gt (Get-Item $destFile).LastWriteTimeUtc) {
            Copy-Item -Path $srcFile.FullName -Destination $destFile -Force
            Write-Host "  [UPD]  $rel" -ForegroundColor Yellow
            $updated++
        }
    }
    return $updated
}

function Sync-SourceTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    if (-not (Test-Path $DestinationDir)) {
        New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
    }

    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        robocopy $SourceDir $DestinationDir /MIR /XD .git __pycache__ .venv models config logs temp installer /XF "*.pyc" /NFL /NDL /NJH /NJS /NC /NS /NP 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prevPref
    }
    if ($LASTEXITCODE -gt 7) { throw "robocopy failed (exit code $LASTEXITCODE)" }
    $LASTEXITCODE = 0
}

function Assert-ValidInstallLayout {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InstallRoot,
        [Parameter(Mandatory = $true)]
        [string]$NestedRepoPath
    )

    if (Test-Path $NestedRepoPath) {
        throw "Invalid install layout: nested repo directory still exists at $NestedRepoPath"
    }

    $requiredPaths = @(
        (Join-Path $InstallRoot "pyproject.toml"),
        (Join-Path $InstallRoot "download_model.py"),
        (Join-Path $InstallRoot "dictator\__main__.py")
    )
    foreach ($path in $requiredPaths) {
        if (-not (Test-Path $path)) {
            throw "Invalid install layout: missing required path $path"
        }
    }
}

# ── WIN-01: Check NVIDIA GPU ─────────────────────────────────────────────────
Write-Step "Checking for NVIDIA GPU..."
try {
    $gpu = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
    if ($gpu) {
        Write-Ok "GPU detected: $($gpu.Trim())"
    } else {
        Write-Warn "No NVIDIA GPU detected. GPU acceleration will not be available."
    }
} catch {
    Write-Warn "nvidia-smi not found. GPU acceleration may not be available."
}

# ── Antimalware notice ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
Write-Host "  │  ANTIMALWARE NOTICE                                            │" -ForegroundColor Yellow
Write-Host "  │                                                                │" -ForegroundColor Yellow
Write-Host "  │  This installer uses uv.exe (by Astral) to manage Python      │" -ForegroundColor Yellow
Write-Host "  │  packages. Some antimalware tools (e.g. Malwarebytes) may      │" -ForegroundColor Yellow
Write-Host "  │  flag or quarantine uv.exe as a false positive.                │" -ForegroundColor Yellow
Write-Host "  │                                                                │" -ForegroundColor Yellow
Write-Host "  │  If this happens, add uv.exe to your antimalware allow-list   │" -ForegroundColor Yellow
Write-Host "  │  before continuing. uv is an open-source Python package       │" -ForegroundColor Yellow
Write-Host "  │  manager (https://github.com/astral-sh/uv) installed via      │" -ForegroundColor Yellow
Write-Host "  │  winget and is required to resolve and sync dependencies.      │" -ForegroundColor Yellow
Write-Host "  └─────────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Both engines (Granite and Cohere) will be installed."
Write-Host ""
Read-Host "  Press Enter to continue"

# ── Install uv ───────────────────────────────────────────────────────────────
Write-Step "Checking for uv package manager..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Already "uv already installed: $(uv --version)"
} else {
    Write-Host "  Installing uv via winget..."
    winget install --id astral-sh.uv --exact --accept-package-agreements --accept-source-agreements
    $machPath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
    $env:PATH = "$userPath;$machPath"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installation succeeded but 'uv' is not on PATH. Restart your terminal and re-run."
    }
    Write-Ok "uv installed: $(uv --version)"
}

$env:UV_PYTHON_PREFERENCE = 'only-system'

# ── Install Python 3.11 ─────────────────────────────────────────────────────
Write-Step "Checking for Python 3.11..."
$py311 = (Get-Command python3.11 -ErrorAction SilentlyContinue).Source
if (-not $py311) {
    try { $py311 = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch { $py311 = $null }
}
if ($py311) {
    Write-Already "Python 3.11 already available: $py311"
} else {
    Write-Host "  Installing Python 3.11 via winget..."
    winget install --id Python.Python.3.11 --exact --accept-package-agreements --accept-source-agreements
    $machPath = [Environment]::GetEnvironmentVariable('PATH', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
    $env:PATH = "$userPath;$machPath"
    $py311 = (Get-Command python3.11 -ErrorAction SilentlyContinue).Source
    if (-not $py311) {
        try { $py311 = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch { $py311 = $null }
    }
    Write-Ok "Python 3.11 installed"
}
if (-not $py311 -or -not (Test-Path $py311)) {
    throw "Python 3.11 is not discoverable after installation. Restart PowerShell and re-run."
}
Write-Ok "Using Python: $py311"

# ── Copy/sync source to install dir ──────────────────────────────────────────
Write-Step "Setting up dictat0r.AI repository..."
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$RepoName = Split-Path -Leaf $RepoRoot
$NestedRepoDir = Join-Path $InstallDir $RepoName

if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
    Write-Host "  ERROR: Cannot find pyproject.toml in $RepoRoot" -ForegroundColor Red
    Write-Host "  Run this script from its location inside the dictat0r.AI repository."
    exit 1
}

if ($RepoRoot -eq $InstallDir) {
    Write-Already "Running from install directory — skipping copy"
} elseif (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Warn "$InstallDir contains an old git clone — replacing with local source..."
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "  Syncing local source contents from $RepoRoot..."
    Sync-SourceTree -SourceDir $RepoRoot -DestinationDir $InstallDir
    Write-Ok "Source installed to $InstallDir from local tree"
} elseif (Test-Path $InstallDir) {
    Write-Warn "$InstallDir exists — updating with local source..."
    if (Test-Path $NestedRepoDir) {
        Write-Warn "Removing stale nested repo copy at $NestedRepoDir..."
        Remove-Item -Recurse -Force $NestedRepoDir
    }
    Sync-SourceTree -SourceDir $RepoRoot -DestinationDir $InstallDir
    Write-Ok "Source synced to $InstallDir"
} else {
    Write-Host "  Syncing local source contents from $RepoRoot..."
    Sync-SourceTree -SourceDir $RepoRoot -DestinationDir $InstallDir
    Write-Ok "Source installed to $InstallDir"
}

Assert-ValidInstallLayout -InstallRoot $InstallDir -NestedRepoPath $NestedRepoDir
Write-Ok "Install layout verified"

# ── Verify & patch outdated files ─────────────────────────────────────────────
if ($RepoRoot -ne $InstallDir) {
    Write-Step "Checking for outdated files in $InstallDir..."
    $outdated = Update-OutdatedFiles -SourceDir $RepoRoot -DestDir $InstallDir
    if ($outdated -eq 0) {
        Write-Already "All files are up-to-date"
    } else {
        Write-Ok "$outdated file(s) updated"
    }
}

# ── Install dependencies ─────────────────────────────────────────────────────
Write-Step "Syncing dependencies..."
Write-Host "  Running uv sync (will skip already-installed packages)..."
Push-Location $InstallDir
Invoke-NativeCommand 'uv sync' ([scriptblock]::Create("uv sync --python `"$py311`" --extra dev"))
Pop-Location
Write-Ok "Dependencies synced"

# ── Validate virtual environment and core imports ─────────────────────────────
Write-Step "Validating virtual environment..."
$venvPython = "$InstallDir\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: Virtual environment not found at $InstallDir\.venv" -ForegroundColor Red
    Write-Host "  Try deleting $InstallDir\.venv and re-running this installer." -ForegroundColor Red
    exit 1
}
$pyVer = & $venvPython --version 2>&1
Write-Ok "venv Python: $pyVer"

Write-Step "Verifying core Python imports..."
$coreImportScript = @'
import sys, importlib
failed = []
for mod in ['PySide6', 'sounddevice', 'soundfile', 'numpy', 'keyboard']:
    try:
        importlib.import_module(mod)
    except ImportError as e:
        failed.append(f'{mod}: {e}')
if failed:
    for f in failed: print(f'FAIL: {f}')
    sys.exit(1)
else:
    print('All core imports OK')
'@
$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $importResult = & $venvPython -c $coreImportScript 2>&1
    foreach ($line in $importResult) { Write-Host "  $line" }
} finally {
    $ErrorActionPreference = $prevPref
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Core dependencies are missing. Try:" -ForegroundColor Red
    Write-Host "    cd '$InstallDir'; uv sync --extra dev" -ForegroundColor Yellow
    exit 1
}
Write-Ok "Core imports verified"

# ── Verify transformers + torch imports ───────────────────────────────────────
Write-Step "Verifying engine dependencies..."
$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try { & $venvPython -c "import transformers; print(f'transformers {transformers.__version__}')" 2>&1 | ForEach-Object { Write-Host "  $_" } }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0) {
    Write-Warn "transformers import failed. Try: cd '$InstallDir'; uv pip install --upgrade 'transformers>=5.4.0'"
} else {
    Write-Ok "transformers import OK"
}

$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try { & $venvPython -c "import torch; print(f'torch {torch.__version__}')" 2>&1 | ForEach-Object { Write-Host "  $_" } }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0) {
    Write-Warn "torch import failed. Both engines require PyTorch."
    Write-Host "  Try: cd '$InstallDir'; uv pip install --index-url https://download.pytorch.org/whl/cu128 torch" -ForegroundColor Yellow
} else {
    Write-Ok "torch import OK"
}

# ── Ensure PyTorch has CUDA support ───────────────────────────────────────────
Write-Step "Verifying PyTorch CUDA support..."
$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try { & $venvPython -c "import torch; assert torch.cuda.is_available()" 2>&1 | Out-Null }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0) {
    Write-Warn "PyTorch does not have CUDA support — reinstalling with CUDA 12.8..."
    Push-Location $InstallDir
    Invoke-NativeCommand 'Install torch+CUDA' {
        uv pip install --python .venv\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu128 --upgrade --force-reinstall torch
    }
    Pop-Location
    Write-Ok "PyTorch with CUDA reinstalled"
} else {
    Write-Already "PyTorch has CUDA support"
}

# Verify GPU kernels actually work (catches arch mismatch, e.g. Blackwell + cu124)
Write-Step "Verifying PyTorch GPU kernel compatibility..."
$prevPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try { & $venvPython -c "import torch; torch.zeros(1, device='cuda')" 2>&1 | Out-Null }
finally { $ErrorActionPreference = $prevPref }
if ($LASTEXITCODE -ne 0) {
    Write-Warn "PyTorch CUDA kernels failed — GPU arch may require a newer CUDA toolkit"
    Write-Host "  Reinstalling torch from cu128 index (includes Blackwell/sm_120 support)..."
    Push-Location $InstallDir
    Invoke-NativeCommand 'Upgrade torch for GPU arch' {
        uv pip install --python .venv\Scripts\python.exe --index-url https://download.pytorch.org/whl/cu128 --upgrade --force-reinstall torch
    }
    Pop-Location
    $prevPref2 = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $venvPython -c "import torch; torch.zeros(1, device='cuda')" 2>&1 | Out-Null }
    finally { $ErrorActionPreference = $prevPref2 }
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "GPU kernel test still fails after torch reinstall — engines will fall back to CPU"
    } else {
        Write-Ok "PyTorch GPU kernels working after reinstall"
    }
} else {
    Write-Ok "PyTorch GPU kernels verified for this GPU"
}

# ── Verify huggingface-hub ────────────────────────────────────────────────────
Write-Step "Checking huggingface-hub version..."
$hfVer = & $venvPython -c "import huggingface_hub; print(huggingface_hub.__version__)" 2>$null
if (-not $hfVer) {
    Write-Host "  huggingface-hub not found, installing..."
    Push-Location $InstallDir
    Invoke-NativeCommand 'Install huggingface-hub' { uv pip install --python .venv\Scripts\python.exe "huggingface-hub>=0.34.0" }
    Pop-Location
    Write-Ok "huggingface-hub installed"
} else {
    Write-Already "huggingface-hub $($hfVer.Trim()) is installed"
}

# ── Verify CUDA DLLs ─────────────────────────────────────────────────────────
Write-Step "Verifying CUDA runtime libraries..."
try {
    $pyScript = @'
import os, sys, importlib.util
spec = importlib.util.find_spec('nvidia')
if spec is None:
    print('SKIP: nvidia pip packages not installed')
    sys.exit(0)
found = []
for sp in spec.submodule_search_locations:
    if not os.path.isdir(sp): continue
    for child in os.listdir(sp):
        bdir = os.path.join(sp, child, 'bin')
        if os.path.isdir(bdir):
            dlls = [f for f in os.listdir(bdir) if f.endswith('.dll')]
            if dlls: found.extend(dlls)
if not found:
    print('WARN: No NVIDIA DLLs found in pip packages')
    sys.exit(1)
cublas = [f for f in found if 'cublas' in f.lower()]
if cublas: print(f'OK: cuBLAS DLLs: {cublas}')
else: print('WARN: cublas DLL not found'); sys.exit(1)
'@
    $cudaCheck = & "$InstallDir\.venv\Scripts\python.exe" -c $pyScript 2>&1
    foreach ($line in $cudaCheck) { Write-Host "  $line" }
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "CUDA runtime libraries verified"
    } else {
        Write-Warn "CUDA DLLs missing — GPU acceleration may fall back to CPU"
    }
} catch {
    Write-Warn "Could not verify CUDA DLLs: $_"
}

# ── Download models ──────────────────────────────────────────────────────────
foreach ($dir in @($ModelsDir, $ConfigDir, $LogsDir, $TempDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# ── Migrate existing data from old locations ──────────────────────────────────
Write-Step "Checking for data to migrate from previous install..."

$oldSettingsFile = "$env:APPDATA\dictat0r.AI\settings.json"
$newSettingsFile = Join-Path $ConfigDir "settings.json"
if ((Test-Path $oldSettingsFile) -and -not (Test-Path $newSettingsFile)) {
    Copy-Item -Path $oldSettingsFile -Destination $newSettingsFile -Force
    Write-Ok "Migrated settings.json from $oldSettingsFile"
} else {
    Write-Already "No settings to migrate (already present or no old settings found)"
}

$oldModelsDir = "$env:LOCALAPPDATA\dictat0r.AI\models"
if (Test-Path $oldModelsDir) {
    $migrated = 0
    foreach ($engineDir in (Get-ChildItem -Path $oldModelsDir -Directory)) {
        $destEngine = Join-Path $ModelsDir $engineDir.Name
        if (-not (Test-Path $destEngine)) {
            Write-Host "  Migrating $($engineDir.Name) model..."
            Copy-Item -Path $engineDir.FullName -Destination $destEngine -Recurse -Force
            $migrated++
            Write-Ok "Migrated $($engineDir.Name) model from $($engineDir.FullName)"
        }
    }
    if ($migrated -eq 0) {
        Write-Already "No models to migrate (already present in new location)"
    }
} else {
    Write-Already "No old model directory found at $oldModelsDir"
}

$oldLogDir = "$env:APPDATA\dictat0r.AI"
foreach ($logFile in @("dictator.log", "dictator.log.1", "dictator.log.2")) {
    $oldLog = Join-Path $oldLogDir $logFile
    $newLog = Join-Path $LogsDir $logFile
    if ((Test-Path $oldLog) -and -not (Test-Path $newLog)) {
        Copy-Item -Path $oldLog -Destination $newLog -Force
    }
}

# ── Download Granite model ────────────────────────────────────────────────────
Write-Step "Checking Granite model (IBM Granite 4.0 1B Speech)..."
$graniteDir = Join-Path $ModelsDir "granite"
if ((Test-Path (Join-Path $graniteDir "config.json"))) {
    Write-Already "Granite model already present in $graniteDir"
} else {
    Write-Host "  Downloading Granite model (ibm-granite/granite-4.0-1b-speech)..."
    Push-Location $InstallDir
    Invoke-StreamingCommand 'Granite model download' { uv run dictator download-model --engine granite --target-dir $ModelsDir }
    Pop-Location
    Write-Ok "Granite model downloaded to $graniteDir"
}

# ── Download Cohere model ─────────────────────────────────────────────────────
Write-Step "Checking Cohere model (Cohere Transcribe 03-2026)..."
$cohereDir = Join-Path $ModelsDir "cohere"
if ((Test-Path (Join-Path $cohereDir "config.json"))) {
    Write-Already "Cohere model already present in $cohereDir"
} else {
    Write-Host "  Downloading Cohere model (CohereLabs/cohere-transcribe-03-2026)..."
    Push-Location $InstallDir
    Invoke-StreamingCommand 'Cohere model download' { uv run dictator download-model --engine cohere --target-dir $ModelsDir }
    Pop-Location
    Write-Ok "Cohere model downloaded to $cohereDir"
}

# ── Write default engine to settings ─────────────────────────────────────────
Write-Step "Configuring default engine..."
$settingsFile = Join-Path $ConfigDir "settings.json"
$cfg = $null
$defaultEngine = 'granite'
if (Test-Path $settingsFile) {
    $rawSettings = Get-Content $settingsFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($rawSettings)) {
        $cfg = $rawSettings | ConvertFrom-Json
    }
}
if (-not $cfg) {
    $cfg = [pscustomobject]@{}
}
if ($cfg.PSObject.Properties.Match('engine').Count -eq 0) {
    $cfg | Add-Member -NotePropertyName 'engine' -NotePropertyValue $defaultEngine
} else {
    $cfg.engine = $defaultEngine
}
$jsonText = $cfg | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($settingsFile, $jsonText, (New-Object System.Text.UTF8Encoding $false))
Write-Ok "Default engine set to '$defaultEngine' in $settingsFile"

# ── Set permissions (current user gets Modify on install dir) ────────────────
Write-Step "Checking directory permissions..."
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$acl = Get-Acl $InstallDir
$existingRule = $acl.Access | Where-Object {
    $_.IdentityReference.Value -eq $currentUser -and
    $_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Modify
}
if ($existingRule) {
    Write-Already "$currentUser already has Modify access on $InstallDir"
} else {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $currentUser,
        [System.Security.AccessControl.FileSystemRights]::Modify,
        ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $InstallDir -AclObject $acl
    Write-Ok "Granted $currentUser Modify access on $InstallDir"
}

# ── Create desktop shortcut ──────────────────────────────────────────────────
Write-Step "Creating desktop shortcut..."
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath "dictat0r.AI.lnk"
if (Test-Path $shortcutPath) {
    Write-Already "Desktop shortcut already exists"
} else {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$InstallDir\.venv\Scripts\pythonw.exe"
    $shortcut.Arguments = "-m dictator"
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "dictat0r.AI — Voice to Text"
    $shortcut.Save()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
    Write-Ok "Desktop shortcut created at $shortcutPath"
}

# ── Windows Defender exclusions ───────────────────────────────────────────────
Write-Step "Configuring Windows Defender exclusions..."
try {
    Add-MpPreference -ExclusionPath $InstallDir -ErrorAction Stop
    Write-Ok "Exclusion added for $InstallDir"
} catch {
    Write-Warn "Could not add Defender exclusion: $_"
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  dictat0r.AI has been installed successfully!" -ForegroundColor Green
Write-Host "  ══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Install dir:    $InstallDir"
Write-Host "  Models:         $ModelsDir"
Write-Host "  Config:         $ConfigDir"
Write-Host "  Logs:           $LogsDir"
Write-Host ""
Write-Host "  Engines:        Granite (default), Cohere"
Write-Host ""
Write-Host "  To launch:      Double-click the desktop shortcut or run:"
Write-Host "    cd '$InstallDir'; uv run dictator"
Write-Host ""
Write-Host "  Default hotkeys:"
Write-Host "    Ctrl+Alt+P   Start recording"
Write-Host "    Ctrl+Alt+L   Stop recording & transcribe"
Write-Host "    Ctrl+Alt+Q   Quit application"
Write-Host ""
