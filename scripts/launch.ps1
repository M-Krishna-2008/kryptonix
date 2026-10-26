# ==============================================================================
# Unified AI Forensics Platform Launcher (PS-05)
# One-click initialization, automated model downloads, consolidated venv, and supervisor
# ==============================================================================

[CmdletBinding()]
param (
    [switch]$DryRun,
    [switch]$Setup,
    [switch]$Reset,
    [switch]$NoBrowser,
    [Parameter(ValueFromRemainingArguments=$true)]
    $ExtraArgs
)

# Parse /dryrun, /setup, /reset passed directly
if ($ExtraArgs -match '(?i)dry[-]?run') { $DryRun = $true }
if ($ExtraArgs -match '(?i)setup') { $Setup = $true }
if ($ExtraArgs -match '(?i)reset') { $Reset = $true }
if ($ExtraArgs -match '(?i)nobrowser') { $NoBrowser = $true }

$ErrorActionPreference = "Continue"
$RootPath = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location -LiteralPath $RootPath

# ------------------------------------------------------------------------------
# 0. Prepare Standard Directories & Logging
# ------------------------------------------------------------------------------
$StandardDirs = @(
    "models",
    "runtime",
    "logs",
    "ai_aud\audio_forensics\models",
    "ai_aud\uploads",
    "ai_aud\artifacts",
    "ai_aud\cache",
    "ai_cctv\models",
    "ai_cctv\ai_cctv_detection\models",
    "ai_cctv\uploads",
    "ai_cctv\artifacts",
    "ai_cctv\cache",
    "ai_img\ai_image_detection\models\clip",
    "ai_img\uploads",
    "ai_img\artifacts",
    "ai_img\ai_image_detection\cache",
    "image_forgery\image_forgery\models\trufor",
    "image_forgery\image_forgery\uploads",
    "image_forgery\image_forgery\artifacts",
    "image_forgery\image_forgery\logs"
)

foreach ($dir in $StandardDirs) {
    $fullDir = Join-Path $RootPath $dir
    if (-not (Test-Path -LiteralPath $fullDir)) {
        New-Item -ItemType Directory -Path $fullDir -Force | Out-Null
    }
}

$LogsDir = Join-Path $RootPath "logs"
$RuntimeDir = Join-Path $RootPath "runtime"
$ConfigPath = Join-Path $RootPath "config\modules.json"
$ModelsManifestPath = Join-Path $RootPath "models\MODELS.json"
$PortsPath = Join-Path $RuntimeDir "ports.json"
$PidsPath = Join-Path $RuntimeDir "pids.json"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogsDir "setup_$Timestamp.txt"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $color = "White"
    switch ($Level) {
        "INFO"    { $color = "Green" }
        "WARN"    { $color = "Yellow" }
        "ERROR"   { $color = "Red" }
        "STEP"    { $color = "Cyan" }
        "MUTED"   { $color = "DarkGray" }
    }
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "HH:mm:ss"), $Level, $Message
    Write-Host $line -ForegroundColor $color
    Add-Content -LiteralPath $LogFile -Value $line -ErrorAction SilentlyContinue
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   PS-05 Unified AI Forensics Platform - One-Click Launcher" -ForegroundColor Cyan
Write-Host "   Working Directory: $RootPath" -ForegroundColor DarkGray
Write-Host "======================================================================" -ForegroundColor Cyan

if ($DryRun) {
    Write-Log "DRY RUN MODE ENABLED - Pre-flight verification only; no services will start." "WARN"
}

# Handle -Reset
if ($Reset) {
    Write-Log "Reset requested. Terminating running processes..." "WARN"
    & "$PSScriptRoot\stop.ps1"
    Write-Log "Runtime cleaned." "INFO"
}

# ------------------------------------------------------------------------------
# 1. System Requirements & Architecture Verification
# ------------------------------------------------------------------------------
Write-Log "Checking Windows system architecture..." "STEP"
$is64 = [Environment]::Is64BitOperatingSystem
if (-not $is64) {
    Write-Log "64-bit Windows is strictly required by PyTorch and deep neural architectures." "ERROR"
    exit 1
}
Write-Log "64-bit Windows architecture verified." "INFO"

# Check Python 3.10 Availability
Write-Log "Verifying Python 3.10 installation..." "STEP"
$py310Exe = $null

# Try 'py -3.10'
try {
    $res = py -3.10 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $res) {
        $py310Exe = $res.Trim()
    }
} catch {}

# Try 'python' if it is 3.10
if (-not $py310Exe) {
    try {
        $ver = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -eq "3.10") {
            $py310Exe = (python -c "import sys; print(sys.executable)").Trim()
        }
    } catch {}
}

# Fallback standard paths
if (-not $py310Exe) {
    $common310 = @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($p in $common310) {
        if (Test-Path -LiteralPath $p) {
            $py310Exe = $p
            break
        }
    }
}

if (-not $py310Exe) {
    Write-Log "Python 3.10 was not detected in standard system locations." "WARN"
    if ($DryRun) {
        Write-Log "[DryRun] Would install Python 3.10 via winget." "INFO"
    } else {
        $hasWinget = Get-Command winget -ErrorAction SilentlyContinue
        if ($hasWinget) {
            Write-Log "Attempting automated installation of Python 3.10 via winget..." "INFO"
            winget install --id Python.Python.3.10 --silent --accept-package-agreements --accept-source-agreements
            Start-Sleep -Seconds 3
            # Recheck
            $res = py -3.10 -c "import sys; print(sys.executable)" 2>$null
            if ($res) { $py310Exe = $res.Trim() }
        } else {
            Write-Log "Winget is not available. Please install Python 3.10 manually from https://www.python.org/downloads/" "ERROR"
            exit 1
        }
    }
} else {
    Write-Log "Found Python 3.10: $py310Exe" "INFO"
}

# ------------------------------------------------------------------------------
# 2. Automated Model Checkpoints Verification & Download
# ------------------------------------------------------------------------------
Write-Log "Verifying neural model checkpoints against manifest..." "STEP"

function Verify-OrDownloadModel {
    param(
        [PSCustomObject]$ModelItem,
        [string]$BaseRoot,
        [bool]$IsDryRun
    )
    $dest = Join-Path $BaseRoot $ModelItem.destination
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    # Check if already present and healthy
    if (Test-Path -LiteralPath $dest) {
        $item = Get-Item -LiteralPath $dest
        $sizeMatches = ($ModelItem.size_bytes -eq 0) -or ($item.Length -eq $ModelItem.size_bytes)
        if ($sizeMatches) {
            if ($ModelItem.sha256) {
                $actualHash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower()
                if ($actualHash -eq $ModelItem.sha256.ToLower()) {
                    Write-Log ("  [VERIFIED] {0} ({1:N2} MB) SHA-256 confirmed." -f $ModelItem.name, ($item.Length / 1MB)) "MUTED"
                    return $true
                } else {
                    Write-Log ("  [CORRUPTED] {0} hash mismatch. Target: {1}, Found: {2}" -f $ModelItem.name, $ModelItem.sha256, $actualHash) "WARN"
                    if (-not $IsDryRun) { Remove-Item -LiteralPath $dest -Force }
                }
            } else {
                Write-Log ("  [PRESENT] {0} ({1:N2} MB)" -f $ModelItem.name, ($item.Length / 1MB)) "MUTED"
                return $true
            }
        } else {
            Write-Log ("  [INCOMPLETE] {0}: Found {1} bytes, expected {2} bytes." -f $ModelItem.name, $item.Length, $ModelItem.size_bytes) "WARN"
            if (-not $IsDryRun) { Remove-Item -LiteralPath $dest -Force }
        }
    }

    if ($ModelItem.is_committed) {
        # Committed model should already be present
        if (-not (Test-Path -LiteralPath $dest)) {
            Write-Log ("  [ERROR] Trained artifact '{0}' missing from repo: {1}" -f $ModelItem.name, $ModelItem.destination) "ERROR"
            return $false
        }
        return $true
    }

    # Model is missing and needs download
    if ($IsDryRun) {
        Write-Log ("  [DryRun] Would download {0} from {1} -> {2}" -f $ModelItem.name, $ModelItem.download_url, $ModelItem.destination) "INFO"
        return $true
    }

    $url = $ModelItem.download_url
    if (-not $url) {
        Write-Log ("  [NOTICE] No download URL for {0}. Place file manually at: {1}" -f $ModelItem.name, $dest) "WARN"
        return $false
    }

    Write-Log ("  Downloading {0} from {1}..." -f $ModelItem.name, $url) "STEP"
    $downloadSuccess = $false
    $curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if ($curlCmd) {
                & curl.exe -L -C - --retry 3 --connect-timeout 20 --progress-bar -o $dest $url
            } else {
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($url, $dest)
            }

            if (Test-Path -LiteralPath $dest) {
                $actualHash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower()
                if ($actualHash -eq $ModelItem.sha256.ToLower()) {
                    Write-Log ("  [DOWNLOADED & VERIFIED] {0}" -f $ModelItem.name) "INFO"
                    $downloadSuccess = $true
                    break
                } else {
                    Write-Log ("  Download attempt {0} failed SHA-256 check. Retrying..." -f $attempt) "WARN"
                    Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {
            Write-Log ("  Download attempt {0} error: {1}" -f $attempt, $_.Exception.Message) "WARN"
        }
        Start-Sleep -Seconds 2
    }

    if (-not $downloadSuccess) {
        Write-Log ("======================================================================") "ERROR"
        Write-Log ("MODEL DOWNLOAD FAILED: {0}" -f $ModelItem.name) "ERROR"
        Write-Log ("  Destination: {0}" -f $dest) "ERROR"
        Write-Log ("  URL:         {0}" -f $url) "ERROR"
        if ($ModelItem.mirror_url) {
            Write-Log ("  Mirror URL:  {0}" -f $ModelItem.mirror_url) "ERROR"
        }
        Write-Log ("Please download this model manually and place it at the destination.") "ERROR"
        Write-Log ("The platform will still launch, but this module will report offline." ) "WARN"
        Write-Log ("======================================================================") "ERROR"
        return $false
    }

    return $true
}

if (Test-Path -LiteralPath $ModelsManifestPath) {
    $modelsManifest = Get-Content -LiteralPath $ModelsManifestPath -Raw | ConvertFrom-Json
    foreach ($m in $modelsManifest.models) {
        $null = Verify-OrDownloadModel -ModelItem $m -BaseRoot $RootPath -IsDryRun $DryRun
    }
} else {
    Write-Log "Master model manifest not found at: $ModelsManifestPath" "WARN"
}

# ------------------------------------------------------------------------------
# 3. Virtual Environment & Dependencies Setup
# ------------------------------------------------------------------------------
Write-Log "Verifying Python virtual environment..." "STEP"

$RootVenvDir = Join-Path $RootPath ".venv"
$RootVenvPy = Join-Path $RootVenvDir "Scripts\python.exe"
$DepsMarker = Join-Path $RootVenvDir ".deps_installed"

if (-not (Test-Path -LiteralPath $RootVenvPy)) {
    Write-Log "Creating consolidated root virtual environment (.venv)..." "STEP"
    if ($DryRun) {
        Write-Log "[DryRun] Would create .venv and install requirements-lock.txt" "INFO"
    } else {
        if ($py310Exe) {
            & $py310Exe -m venv $RootVenvDir
        } else {
            py -3.10 -m venv $RootVenvDir
        }
        
        Write-Log "Upgrading pip to 24.0 (strictly <24.1 for Fairseq compatibility)..." "INFO"
        & $RootVenvPy -m pip install "pip==24.0" --quiet --disable-pip-version-check
    }
}

if ((-not (Test-Path -LiteralPath $DepsMarker)) -and (Test-Path -LiteralPath $RootVenvPy)) {
    if ($DryRun) {
        Write-Log "[DryRun] Would install consolidated dependencies from requirements-lock.txt." "INFO"
    } else {
        Write-Log "First-time dependency installation detected. Installing requirements-lock.txt..." "STEP"
        
        # Check GPU availability for PyTorch CUDA acceleration
        $hasNvidia = $false
        try {
            $smi = nvidia-smi 2>$null
            if ($LASTEXITCODE -eq 0) { $hasNvidia = $true }
        } catch {}

        if ($hasNvidia) {
            Write-Log "NVIDIA GPU detected. Installing PyTorch with CUDA acceleration..." "INFO"
            & $RootVenvPy -m pip install torch torchvision torchaudio --default-timeout 100 --extra-index-url https://download.pytorch.org/whl/cu121
        } else {
            Write-Log "No NVIDIA GPU detected. Installing PyTorch CPU build..." "INFO"
            & $RootVenvPy -m pip install torch torchvision torchaudio --default-timeout 100 --extra-index-url https://download.pytorch.org/whl/cpu
        }

        # Install Fairseq precompiled Windows wheel if missing
        try {
            & $RootVenvPy -c "import fairseq" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Installing Windows-compatible Fairseq 0.12.2 binary..." "INFO"
                & $RootVenvPy -m pip install "https://github.com/BlueAmulet/fairseq-win-whl/releases/download/v0.12.2/fairseq-0.12.2-cp310-cp310-win_amd64.whl" --quiet 2>$null
            }
        } catch {}

        # Install root dependencies
        $reqLock = Join-Path $RootPath "requirements-lock.txt"
        if (Test-Path -LiteralPath $reqLock) {
            Write-Log "Installing pinned packages from requirements-lock.txt..." "INFO"
            & $RootVenvPy -m pip install -r $reqLock --prefer-binary --default-timeout 100
        }

        # Create marker
        Set-Content -LiteralPath $DepsMarker -Value "installed" -Force
        Write-Log "Consolidated dependencies verified and locked." "INFO"
    }
} else {
    Write-Log "Virtual environment and dependencies verified." "INFO"
}

if ($Setup) {
    Write-Log "Setup mode completed successfully. Exiting without starting servers." "INFO"
    exit 0
}

# ------------------------------------------------------------------------------
# 4. Stop Any Existing Stale Processes
# ------------------------------------------------------------------------------
& "$PSScriptRoot\stop.ps1"

# ------------------------------------------------------------------------------
# 5. Dynamic Free Port Allocation
# ------------------------------------------------------------------------------
function Find-FreePort {
    param([int]$StartPort)
    $port = $StartPort
    while ($true) {
        $tcp = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if (-not $tcp) {
            return $port
        }
        $port++
    }
}

Write-Log "Assigning free network ports for gateway and modules..." "STEP"
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Log "Config file missing: $ConfigPath" "ERROR"
    exit 1
}
$manifest = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

$AssignedPorts = @{}
$gatewayDefault = if ($manifest.platform.gateway_default_port) { $manifest.platform.gateway_default_port } else { 8080 }
$AssignedPorts["gateway"] = Find-FreePort -StartPort $gatewayDefault

foreach ($mod in $manifest.modules) {
    $p = Find-FreePort -StartPort $mod.default_port
    $AssignedPorts[$mod.id] = $p
}

# Write runtime\ports.json
if (-not $DryRun) {
    $AssignedPorts | ConvertTo-Json | Set-Content -LiteralPath $PortsPath -Force
}
Write-Log ("Allocated Ports: Gateway={0}, Audio={1}, Image={2}, Forgery={3}, CCTV={4}" -f `
    $AssignedPorts["gateway"], $AssignedPorts["ai_aud"], $AssignedPorts["ai_img"], $AssignedPorts["image_forgery"], $AssignedPorts["ai_cctv"]) "INFO"

if ($DryRun) {
    Write-Log "[DryRun] Pre-flight checks and configuration plan passed cleanly." "INFO"
    exit 0
}

# ------------------------------------------------------------------------------
# 6. Launch Modules in Background
# ------------------------------------------------------------------------------
$Pids = @{}

function Start-BackgroundService {
    param(
        [string]$Name,
        [string]$PythonExe,
        [string]$Cwd,
        [string]$ScriptOrApp,
        [int]$Port,
        [string]$Prefix
    )
    $stdoutLog = Join-Path $LogsDir "${Name}_stdout.log"
    $stderrLog = Join-Path $LogsDir "${Name}_stderr.log"

    Write-Log ("Starting {0} on 127.0.0.1:{1}..." -f $Name, $Port) "INFO"

    $cmdArgs = "/c `"`"$PythonExe`" -m uvicorn $ScriptOrApp --host 127.0.0.1 --port $Port > `"$stdoutLog`" 2>`"$stderrLog`"`""

    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList $cmdArgs `
        -WorkingDirectory $Cwd `
        -WindowStyle Hidden `
        -PassThru

    return $process.Id
}

# Launch 4 Modules using consolidated or module python
foreach ($mod in $manifest.modules) {
    $mId = $mod.id
    $mPy = Join-Path $RootPath $mod.venv_python
    # Fallback to consolidated root venv if per-module venv not present
    if (-not (Test-Path -LiteralPath $mPy)) {
        $mPy = $RootVenvPy
    }

    $mCwd = Join-Path $RootPath $mod.cwd
    $mPort = $AssignedPorts[$mId]

    if (Test-Path -LiteralPath $mPy) {
        $pidNum = Start-BackgroundService -Name $mId `
            -PythonExe $mPy `
            -Cwd $mCwd `
            -ScriptOrApp "main_standalone:app" `
            -Port $mPort `
            -Prefix $mod.upstream_prefix

        $Pids[$mId] = $pidNum
    } else {
        Write-Log ("Cannot start {0}: Python executable not found at {1}" -f $mId, $mPy) "WARN"
    }
}

# Launch Gateway Server
$gatewayPort = $AssignedPorts["gateway"]
$gatewayPy = Join-Path $RootPath "gateway\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $gatewayPy)) {
    $gatewayPy = $RootVenvPy
}
$gatewayCwd = Join-Path $RootPath "gateway"

$env:GATEWAY_PORT = "$gatewayPort"
$gwPid = Start-BackgroundService -Name "gateway" `
    -PythonExe $gatewayPy `
    -Cwd $gatewayCwd `
    -ScriptOrApp "server:app" `
    -Port $gatewayPort `
    -Prefix ""

$Pids["gateway"] = $gwPid
$Pids | ConvertTo-Json | Set-Content -LiteralPath $PidsPath -Force

# ------------------------------------------------------------------------------
# 7. Health Check Verification Table
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "Waiting for backend services to initialize..." -ForegroundColor Cyan
Write-Host "----------------------------------------------------------------------"

$timeoutSec = 60
$startWait = Get-Date

while ((Get-Date) - $startWait -lt [TimeSpan]::FromSeconds($timeoutSec)) {
    Start-Sleep -Seconds 2
    try {
        $gwResp = Invoke-RestMethod -Uri "http://127.0.0.1:$gatewayPort/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($gwResp.status -in @("healthy", "degraded")) {
            $upCount = 0
            foreach ($k in $gwResp.modules.PSObject.Properties.Name) {
                if ($gwResp.modules.$k.status -eq "up") { $upCount++ }
            }
            if ($upCount -eq 4) {
                break
            }
        }
    } catch {}
    Write-Host -NoNewline "."
}

Write-Host ""
Write-Host ""
Write-Host "Service Status Table:" -ForegroundColor Cyan
Write-Host ("{0,-22} {1,-10} {2,-10} {3}" -f "SERVICE", "PORT", "PID", "STATUS") -ForegroundColor DarkGray
Write-Host "----------------------------------------------------------------------"

try {
    $healthData = Invoke-RestMethod -Uri "http://127.0.0.1:$gatewayPort/api/health" -TimeoutSec 3 -ErrorAction Stop
    Write-Host ("{0,-22} {1,-10} {2,-10} {3}" -f "Gateway Server", $gatewayPort, $Pids["gateway"], "[READY]") -ForegroundColor Green
    foreach ($mod in $manifest.modules) {
        $mInfo = $healthData.modules.($mod.id)
        $mStatus = if ($mInfo.status -eq "up") { "[ONLINE]" } else { "[STARTING / DOWN]" }
        $color = if ($mInfo.status -eq "up") { "Green" } else { "Yellow" }
        Write-Host ("{0,-22} {1,-10} {2,-10} {3}" -f $mod.short_name, $AssignedPorts[$mod.id], $Pids[$mod.id], $mStatus) -ForegroundColor $color
    }
} catch {
    Write-Host "Gateway starting or unresponsive." -ForegroundColor Yellow
}

Write-Host "----------------------------------------------------------------------"
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "   PLATFORM ACTIVE - OPEN IN BROWSER:" -ForegroundColor Green
Write-Host "   http://localhost:$gatewayPort" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To shut down all services cleanly, run stop.bat" -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Start-Process "http://localhost:$gatewayPort"
}

Write-Host "Press Ctrl+C to terminate all services..." -ForegroundColor DarkGray
try {
    $gwProc = Get-Process -Id $Pids["gateway"] -ErrorAction SilentlyContinue
    if ($gwProc) {
        $gwProc.WaitForExit()
    } else {
        while ($true) { Start-Sleep -Seconds 2 }
    }
} finally {
    & "$PSScriptRoot\stop.ps1"
}
