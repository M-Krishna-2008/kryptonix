@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================================================
echo  PS-05 AI Image Detection - System ^& Portability Diagnostics
echo =========================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$os = (Get-CimInstance Win32_OperatingSystem).Caption; " ^
    "$osVer = (Get-CimInstance Win32_OperatingSystem).Version; " ^
    "$is64 = [Environment]::Is64BitOperatingSystem; " ^
    "$curDrive = (Get-Item .).Root.Name; " ^
    "$driveLetter = $curDrive.TrimEnd(':\'); " ^
    "$freeBytes = (Get-PSDrive $driveLetter).Free; " ^
    "$freeGB = [math]::Round(($freeBytes / 1GB), 2); " ^
    "Write-Host '[SYSTEM OS & HARDWARE]'; " ^
    "Write-Host ('  - Operating System  : ' + $os + ' (' + $osVer + ')'); " ^
    "Write-Host ('  - Architecture      : ' + $(if ($is64) { '64-bit (x64) [Supported]' } else { '32-bit [UNSUPPORTED]' })); " ^
    "Write-Host ('  - Target Disk Free  : ' + $freeGB + ' GB free on ' + $curDrive + $(if ($freeGB -lt 10) { ' [WARNING: Low space, <10GB]' } else { ' [OK]' })); " ^
    "Write-Host ''; " ^
    "Write-Host '[REQUIRED PREREQUISITES]'; " ^
    "$wingetCmd = Get-Command winget -ErrorAction SilentlyContinue; " ^
    "Write-Host ('  - winget            : ' + $(if ($wingetCmd) { 'Found (' + $wingetCmd.Source + ')' } else { 'NOT FOUND (Manual install required on older Win10)' })); " ^
    "$pyCmd = Get-Command py -ErrorAction SilentlyContinue; " ^
    "$pythonCmd = Get-Command python -ErrorAction SilentlyContinue; " ^
    "if ($pyCmd) { " ^
    "  $pyVer = & py -3.10 -c 'import sys; print(sys.version.split()[0])' 2>$null; " ^
    "  if ($pyVer) { Write-Host ('  - Python 3.10       : Found via py launcher (' + $pyVer + ')') } " ^
    "  else { $pyAny = & py --version 2>$null; Write-Host ('  - Python (Active)   : ' + $pyAny + ' (py -3.10 not registered)') } " ^
    "} elseif ($pythonCmd) { " ^
    "  $pVer = & python --version 2>$null; " ^
    "  Write-Host ('  - Python (Active)   : ' + $pVer); " ^
    "} else { " ^
    "  Write-Host '  - Python 3.10+      : NOT FOUND'; " ^
    "} " ^
    "$vc = (Test-Path 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') -or (Test-Path 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') -or (Test-Path ($env:SystemRoot + '\System32\vcruntime140.dll')); " ^
    "Write-Host ('  - VC++ Redist 2015+ : ' + $(if ($vc) { 'Installed [OK]' } else { 'MISSING (Required by PyTorch)' })); " ^
    "Write-Host ''; " ^
    "Write-Host '[OPTIONAL TOOLS AUDIT]'; " ^
    "$gitCmd = Get-Command git -ErrorAction SilentlyContinue; " ^
    "Write-Host ('  - git               : ' + $(if ($gitCmd) { 'Found (' + $gitCmd.Source + ')' } else { 'Not installed (NOT NEEDED: CLIP installed via zip)' })); " ^
    "$ffCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue; " ^
    "Write-Host ('  - ffmpeg            : ' + $(if ($ffCmd) { 'Found' } else { 'Not installed (NOT NEEDED: image-only module)' })); " ^
    "$nodeCmd = Get-Command node -ErrorAction SilentlyContinue; " ^
    "Write-Host ('  - node / npm        : ' + $(if ($nodeCmd) { 'Found' } else { 'Not installed (NOT NEEDED: pure Vanilla JS frontend)' })); " ^
    "$smiCmd = Get-Command nvidia-smi -ErrorAction SilentlyContinue; " ^
    "Write-Host ('  - nvidia-smi (GPU)  : ' + $(if ($smiCmd) { 'Found (CUDA acceleration enabled)' } else { 'Not found (CPU fallback mode active)' })); " ^
    "Write-Host ''; " ^
    "Write-Host '[NETWORK REACHABILITY (SETUP ONLY)]'; " ^
    "function Test-Url($u) { try { $req = [System.Net.WebRequest]::Create($u); $req.Method = 'HEAD'; $req.Timeout = 4000; $resp = $req.GetResponse(); $resp.Close(); return $true } catch [System.Net.WebException] { if ($_.Exception.Response) { return $true }; return $false } catch { return $false } } " ^
    "$pypiOk = Test-Url 'https://pypi.org'; " ^
    "$azureOk = Test-Url 'https://openaipublic.azureedge.net'; " ^
    "$ghOk = Test-Url 'https://raw.githubusercontent.com'; " ^
    "Write-Host ('  - PyPI (pypi.org)   : ' + $(if ($pypiOk) { 'Reachable [OK]' } else { 'UNREACHABLE (Offline setup blocked)' })); " ^
    "Write-Host ('  - OpenAI Azure CDN  : ' + $(if ($azureOk) { 'Reachable [OK]' } else { 'UNREACHABLE (Weight download blocked)' })); " ^
    "Write-Host ('  - GitHub Raw Host   : ' + $(if ($ghOk) { 'Reachable [OK]' } else { 'UNREACHABLE (Probe download blocked)' })); " ^
    "Write-Host ''; " ^
    "Write-Host '[MODEL WEIGHT FILES INTEGRITY]'; " ^
    "$vitPath = 'ai_image_detection\models\clip\ViT-L-14.pt'; " ^
    "if (-not (Test-Path $vitPath)) { $vitPath = 'ai_image_detection\models\ViT-L-14.pt'; } " ^
    "if (Test-Path $vitPath) { " ^
    "  $vitItem = Get-Item $vitPath; " ^
    "  $vitMB = [math]::Round(($vitItem.Length / 1MB), 2); " ^
    "  $vitOk = $vitItem.Length -eq 932768134; " ^
    "  Write-Host ('  - ViT-L-14.pt       : Present (' + $vitMB + ' MB) ' + $(if ($vitOk) { '[Integrity OK: 932,768,134 bytes]' } else { '[WARNING: Size mismatch]' })); " ^
    "} else { " ^
    "  Write-Host '  - ViT-L-14.pt       : MISSING (Will download on first run)'; " ^
    "} " ^
    "$probePath = 'ai_image_detection\models\fc_weights.pth'; " ^
    "if (Test-Path $probePath) { " ^
    "  $probeItem = Get-Item $probePath; " ^
    "  $probeOk = $probeItem.Length -eq 4083; " ^
    "  Write-Host ('  - fc_weights.pth    : Present (' + $probeItem.Length + ' bytes) ' + $(if ($probeOk) { '[Integrity OK: 4,083 bytes]' } else { '[WARNING: Size mismatch]' })); " ^
    "} else { " ^
    "  Write-Host '  - fc_weights.pth    : MISSING (Will download on first run)'; " ^
    "} "

echo.
echo =========================================================================
echo  Diagnostics Complete.
echo =========================================================================
if "%~1" neq "/nopause" pause
