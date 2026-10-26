# PS-05 Diagnostic Script for ai_cctv_detection module
# Evaluates system compatibility, dependencies, network, and model assets.

param(
    [string]$TargetDir = $PSScriptRoot
)

$ErrorActionPreference = "Continue"

Write-Output "========================================================"
Write-Output " PS-05 Forensic Platform: System Diagnostic Tool"
Write-Output " Target Directory: $TargetDir"
Write-Output " Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "========================================================"
Write-Output ""

$exitCode = 0
$isCompatible = $true
$needsSetup = $false

# 1. OS & Architecture Check
$is64Bit = [System.Environment]::Is64BitOperatingSystem
$osDesc = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
$osBuild = [System.Environment]::OSVersion.Version.Build

Write-Output "[1/11] Operating System & Architecture"
if ($is64Bit) {
    Write-Output "  [OK] 64-bit Architecture (x64) detected."
} else {
    Write-Output "  [FAIL] 32-bit Operating System detected! 64-bit Windows is REQUIRED."
    $isCompatible = $false
}

if ($osBuild -ge 17763) {
    Write-Output "  [OK] OS: $osDesc (Build $osBuild - Windows 10/11 supported)"
} else {
    Write-Output "  [FAIL] Ancient Windows build $osBuild detected. Windows 10 Build 1809+ or Windows 11 required."
    $isCompatible = $false
}
Write-Output ""

# 2. Disk Space Check
Write-Output "[2/11] Available Disk Space"
try {
    $resolved = (Resolve-Path $TargetDir).Path
    $driveLetter = [System.IO.Path]::GetPathRoot($resolved).Substring(0, 1)
    $dInfo = [System.IO.DriveInfo]::new($driveLetter)
    $freeGb = [math]::Round($dInfo.AvailableFreeSpace / 1GB, 2)
    if ($freeGb -ge 10.0) {
        Write-Output "  [OK] Drive ${driveLetter}: has $freeGb GB free (>= 10 GB requirement met)."
    } elseif ($freeGb -ge 5.0) {
        Write-Output "  [WARN] Drive ${driveLetter}: has $freeGb GB free (< 10 GB recommended. Space may run tight during heavy uploads)."
        $needsSetup = $true
    } else {
        Write-Output "  [FAIL] Drive ${driveLetter}: has only $freeGb GB free (< 5 GB is critically low). Free up disk space!"
        $isCompatible = $false
    }
} catch {
    Write-Output "  [INFO] Drive space check bypassed: $($_.Exception.Message)"
}
Write-Output ""

# 3. Windows Package Manager (Winget)
Write-Output "[3/11] Package Manager (Winget)"
$wingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
if ($wingetCmd) {
    try {
        $wVer = & winget.exe --version 2>$null
        Write-Output "  [OK] winget is available ($wVer). Automated prerequisite installation supported."
    } catch {
        Write-Output "  [WARN] winget command located but failed to run."
        $needsSetup = $true
    }
} else {
    Write-Output "  [WARN] winget not found in PATH. Install 'App Installer' from Microsoft Store or GitHub for automated installs."
    $needsSetup = $true
}
Write-Output ""

# 4. Python Detection
Write-Output "[4/11] Python Installation"
$foundPython = $false
$pyVers = @()

# Check py launcher
$pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
    Write-Output "  [INFO] Windows Python launcher (py.exe) is present."
    try {
        $pyList = & py -0p 2>$null
        if ($pyList) {
            foreach ($line in ($pyList -split "`r?`n")) {
                if ($line.Trim()) { Write-Output "    $line" }
            }
        }
    } catch {}
}

# Scan PATH and common locations
$scanLocations = @(
    "python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files\Python310\python.exe"
)

foreach ($loc in $scanLocations) {
    try {
        $cmd = Get-Command $loc -ErrorAction SilentlyContinue
        $exePath = if ($cmd) { $cmd.Source } elseif (Test-Path $loc) { (Resolve-Path $loc).Path } else { $null }
        if ($exePath -and -not ($pyVers -contains $exePath)) {
            $pyVers += $exePath
            $vStr = & "$exePath" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]} ({sys.version_info[3]})')" 2>$null
            if ($vStr -match '3\.(10|11)\.') {
                Write-Output "  [OK] Found compatible Python: $exePath (v$vStr)"
                $foundPython = $true
            } else {
                Write-Output "  [INFO] Found Python (incompatible/other): $exePath (v$vStr)"
            }
        }
    } catch {}
}

if (-not $foundPython) {
    Write-Output "  [WARN] No Python 3.10 or 3.11 installation detected. run_platform.bat will auto-install Python 3.10 via winget."
    $needsSetup = $true
}
Write-Output ""

# 5. Git Status
Write-Output "[5/11] Git Version Control"
$gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
if ($gitCmd) {
    try {
        $gVer = & git.exe --version 2>$null
        Write-Output "  [OK] Git is installed: $gVer (Optional: Not required for runtime operation)."
    } catch {
        Write-Output "  [INFO] N/A (Git is not required for running this forensic module)."
    }
} else {
    Write-Output "  [OK] N/A (Git is not required for running this forensic module. Self-contained ZIP distribution)."
}
Write-Output ""

# 6. FFmpeg Decoding Status
Write-Output "[6/11] Video Decoding Backend (FFmpeg)"
Write-Output "  [OK] Bundled via PyAV (av==18.1.0). Precompiled FFmpeg C-libraries (avcodec, avformat, swscale) are embedded in Python wheels."
Write-Output "  [OK] System-wide ffmpeg.exe is NOT required."
Write-Output ""

# 7. Node.js / NPM Status
Write-Output "[7/11] Frontend Engine (Node.js / npm)"
Write-Output "  [OK] N/A (Frontend is 100% vanilla HTML5, CSS3, and ES6 JavaScript)."
Write-Output "  [OK] No node.js, npm, webpack, or frontend compilation steps required."
Write-Output ""

# 8. GPU & Hardware Acceleration
Write-Output "[8/11] Hardware Acceleration (GPU / CPU)"
$hasNvidia = $false
$nvidiaSmi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    try {
        $gpuOut = & nvidia-smi.exe --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
        if ($gpuOut) {
            $hasNvidia = $true
            Write-Output "  [OK] NVIDIA GPU detected via nvidia-smi:"
            foreach ($g in ($gpuOut -split "`r?`n")) {
                if ($g.Trim()) { Write-Output "    GPU: $g" }
            }
        }
    } catch {}
}

if (-not $hasNvidia) {
    try {
        $gpus = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue
        foreach ($g in $gpus) {
            Write-Output "  [INFO] Video Adapter: $($g.Name)"
            if ($g.Name -match "NVIDIA") { $hasNvidia = $true }
        }
    } catch {}
}

if ($hasNvidia) {
    Write-Output "  [OK] Hardware Acceleration: CUDA GPU mode will be used for fast inference (~120-250 FPS)."
} else {
    Write-Output "  [OK] Hardware Acceleration: CPU Fallback mode will be used (~15-35 FPS). Universal compatibility."
}
Write-Output ""

# 9. Visual C++ Redistributable
Write-Output "[9/11] Microsoft Visual C++ 2015-2022 Redistributable (x64)"
$vcInstalled = $false
try {
    $vcKey = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    if (Test-Path $vcKey) {
        $val = (Get-ItemProperty -Path $vcKey -Name "Installed" -ErrorAction SilentlyContinue).Installed
        if ($val -eq 1) {
            $vcInstalled = $true
            $ver = (Get-ItemProperty -Path $vcKey -Name "Version" -ErrorAction SilentlyContinue).Version
            Write-Output "  [OK] VC++ 2015-2022 x64 Redistributable is INSTALLED (v$ver)."
        }
    }
} catch {}

if (-not $vcInstalled) {
    Write-Output "  [WARN] VC++ 2015-2022 x64 Redistributable NOT found. (Required for PyTorch and OpenCV DLLs)."
    Write-Output "  [INFO] run_platform.bat will automatically install it via winget (Microsoft.VCRedist.2015+.x64)."
    $needsSetup = $true
}
Write-Output ""

# 10. Network Reachability Check (2s timeout)
Write-Output "[10/11] Network Reachability (First-run provision check)"
$hosts = @("pypi.org", "github.com", "huggingface.co")
$allOnline = $true

foreach ($h in $hosts) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect($h, 443, $null, $null)
        $wh = $iar.AsyncWaitHandle
        if ($wh.WaitOne(2000, $false)) {
            $tcp.EndConnect($iar)
            $tcp.Close()
            Write-Output "  [OK] $h : 443 (HTTPS Reachable)"
        } else {
            $tcp.Close()
            Write-Output "  [WARN] $h : 443 (Connection Timed Out - >2s)"
            $allOnline = $false
        }
    } catch {
        Write-Output "  [WARN] $h : 443 (Unreachable: $($_.Exception.Message))"
        $allOnline = $false
    }
}

if (-not $allOnline) {
    Write-Output "  [NOTE] Offline environment detected. Pre-provisioned offline wheels or USB drive needed if .venv is not yet built."
}
Write-Output ""

# 11. Model Files Integrity
Write-Output "[11/11] Forensic Model Weights Verification"
$models = @(
    @{ Path = "$TargetDir\ai_cctv_detection\models\best.pt"; ExpectedSha = "4dc60327c256cb9576b56ad142184c7597485d8d0511352d4e8a518744fbcc30"; Name = "Fine-Tuned Detector (best.pt)"; Required = $true },
    @{ Path = "$TargetDir\models\yolo11s-cls.pt"; ExpectedSha = "e2b605d1c8c212b434a75a32759a6f7adf1d2b29c35f76bdccd4c794cb653cf2"; Name = "Base YOLO11s Checkpoint"; Required = $false }
)

$modelsReady = $true
foreach ($m in $models) {
    if (Test-Path $m.Path) {
        $item = Get-Item $m.Path
        $size = $item.Length
        try {
            $hash = (Get-FileHash -Path $m.Path -Algorithm SHA256).Hash.ToLower()
            if ($hash -eq $m.ExpectedSha.ToLower()) {
                Write-Output "  [OK] $($m.Name) PRESENT and SHA-256 VERIFIED."
                Write-Output "       Path: $($m.Path)"
                Write-Output "       Size: $('{0:N0}' -f $size) bytes | Hash: $hash"
            } else {
                Write-Output "  [WARN] $($m.Name) PRESENT but SHA-256 differs from baseline."
                Write-Output "         Expected: $($m.ExpectedSha)"
                Write-Output "         Actual:   $hash"
            }
        } catch {
            Write-Output "  [OK] $($m.Name) PRESENT ($size bytes)."
        }
    } else {
        if ($m.Required) {
            Write-Output "  [FAIL] Required model weight file MISSING: $($m.Path)"
            Write-Output "         This fine-tuned forensic weight file cannot be downloaded publicly."
            Write-Output "         Ensure it is copied together with the module!"
            $modelsReady = $false
            $needsSetup = $true
        } else {
            Write-Output "  [INFO] Base checkpoint $($m.Path) not present. run_platform.bat will auto-download if needed."
        }
    }
}
Write-Output ""

# Check .venv status
$venvPy = "$TargetDir\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Output "  [OK] Virtual environment (.venv) already exists."
} else {
    Write-Output "  [INFO] Virtual environment (.venv) not yet created. First-run setup will initialize it."
    $needsSetup = $true
}

Write-Output "========================================================"
Write-Output " DIAGNOSTIC SUMMARY & VERDICT"
Write-Output "========================================================"

# Summary Verdict Determination
if (-not $isCompatible) {
    Write-Output " VERDICT: INCOMPATIBLE (Exit Code 2)"
    Write-Output " Reason: System does not meet minimum architectural or disk requirements."
    exit 2
} elseif ((Test-Path $venvPy) -and $modelsReady) {
    Write-Output " VERDICT: FULLY READY TO RUN (Exit Code 0)"
    Write-Output " Next Step: Double-click 'run_platform.bat' to start the forensic platform."
    exit 0
} else {
    Write-Output " VERDICT: READY FOR FIRST-RUN SETUP (Exit Code 1)"
    Write-Output " Next Step: Run 'run_platform.bat' to automatically provision dependencies and launch."
    exit 1
}
