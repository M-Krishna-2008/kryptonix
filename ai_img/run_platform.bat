@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ---------------------------------------------------------------------------
:: PS-05 Digital Evidence Authenticity & Integrity Verification Platform
:: Self-Provisioning Clean-Room Launcher for Windows 10/11
:: ---------------------------------------------------------------------------

:: Parse CLI flags immediately
set NO_PAUSE=0
if /i "%~1"=="/nopause" set NO_PAUSE=1
if /i "%~2"=="/nopause" set NO_PAUSE=1
if /i "%~3"=="/nopause" set NO_PAUSE=1

if /i "%~1"=="/dryrun" goto :execute_dryrun
if /i "%~2"=="/dryrun" goto :execute_dryrun
if /i "%~3"=="/dryrun" goto :execute_dryrun

if /i "%~1"=="/reset" goto :handle_reset
if /i "%~2"=="/reset" goto :handle_reset
if /i "%~3"=="/reset" goto :handle_reset
goto :start_real_launcher

:handle_reset
echo [RESET] Clean reinstall requested (/reset flag detected).
if exist ".venv" rmdir /s /q ".venv" >nul 2>&1
if exist ".deps_installed" del /f /q ".deps_installed" >nul 2>&1
echo [RESET] .venv and dependency markers deleted.
echo.

:start_real_launcher
set APP_MODULE=main_standalone:app
set APP_NAME=PS-05 Digital Evidence Platform - AI Image Detection
set DEFAULT_PORT=8000

:: Setup logging directory & timestamp (YYYYMMDD_HHMMSS)
if not exist "logs" mkdir "logs"
set DT=
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul') do set DT=%%I
if "%DT%"=="" set DT=session
set LOG_FILE=logs\setup_%DT%.txt

call :log "========================================================================="
call :log " %APP_NAME%"
call :log " 100 Percent Local Forensic Verification Launcher"
call :log " Session Log: %LOG_FILE%"
call :log "========================================================================="
call :log ""

:: ---------------------------------------------------------------------------
:: [1/7] System Architecture, OS Version & Disk Space Check
:: ---------------------------------------------------------------------------
call :log "[1/7] Inspecting system environment and disk storage..."

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$is64 = [Environment]::Is64BitOperatingSystem; " ^
    "if (-not $is64) { exit 2 }; " ^
    "$drive = (Get-Item .).Root.Name.TrimEnd(':\'); " ^
    "$freeBytes = (Get-PSDrive $drive).Free; " ^
    "$freeGB = [math]::Round(($freeBytes / 1GB), 2); " ^
    "Write-Host ('System: 64-bit OS verified | Free Disk Space: ' + $freeGB + ' GB on drive ' + $drive + ':'); " ^
    "if ($freeGB -lt 10.0) { exit 3 }" >> "%LOG_FILE%" 2>&1
set SYS_CHECK_ERR=%errorlevel%

if "%SYS_CHECK_ERR%"=="2" goto :fail_os_64
if "%SYS_CHECK_ERR%"=="3" goto :warn_disk_space
call :log "[1/7] System check passed (64-bit Windows, sufficient disk space)."
goto :step_prereqs

:fail_os_64
call :log "[ERROR] This platform requires a 64-bit (x64) Windows operating system."
goto :fail_pause

:warn_disk_space
call :log "[WARNING] Free disk space is below 10 GB. Please ensure sufficient disk space."

:step_prereqs
:: ---------------------------------------------------------------------------
:: [2/7] Locate or Auto-Provision Prerequisites (Python 3.10, VC++ Redist)
:: ---------------------------------------------------------------------------
call :log "[2/7] Checking runtime prerequisites (Python 3.10 and VC++ Redistributable)..."

:: Check for VC++ 2015-2022 Redistributable
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$vc = (Test-Path 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') -or (Test-Path 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') -or (Test-Path ($env:SystemRoot + '\System32\vcruntime140.dll')); " ^
    "if ($vc) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 goto :vc_present

call :log "[2/7] Microsoft Visual C++ 2015-2022 Redistributable is missing."
where winget >nul 2>&1
if errorlevel 1 goto :vc_winget_missing

call :log "[2/7] Installing Microsoft Visual C++ Redistributable via winget..."
winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
call :log "[2/7] VC++ Redistributable installation triggered."
goto :check_python

:vc_winget_missing
call :log "[ERROR] winget is not available to install VC++ Redistributable."
call :log "Please download and install it manually from:"
call :log "  https://aka.ms/vs/17/release/vc_redist.x64.exe"
goto :fail_pause

:vc_present
call :log "[2/7] Microsoft Visual C++ Redistributable is present."

:check_python
set PYTHON_CMD=
py -3.10 -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.10
if defined PYTHON_CMD goto :python_ready

py -3.11 -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.11
if defined PYTHON_CMD goto :python_ready

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 14) else 1)" >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=python
if defined PYTHON_CMD goto :python_ready

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" goto :found_local_py310
goto :py_missing

:found_local_py310
set "PATH=%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;!PATH!"
set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
goto :python_ready

:py_missing
call :log "[2/7] Python 3.10+ was not found on your system."
where winget >nul 2>&1
if errorlevel 1 goto :python_manual_required

call :log "[2/7] Auto-provisioning Python 3.10 via winget (silent)..."
winget install --id Python.Python.3.10 --silent --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" goto :found_local_py310
py -3.10 -c "import sys; sys.exit(0)" >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py -3.10
if defined PYTHON_CMD goto :python_ready

:python_manual_required
call :log ""
call :log "========================================================================="
call :log " [ACTION REQUIRED] Python 3.10+ could not be automatically installed."
call :log " Please install Python 3.10 manually:"
call :log "   Official Installer: https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
call :log ""
call :log " IMPORTANT: Check the box: [X] 'Add Python to PATH' during installation."
call :log " Once installed, double-click run_platform.bat again."
call :log "========================================================================="
call :log ""
goto :fail_pause

:python_ready
call :log "[2/7] Using Python interpreter: %PYTHON_CMD%"

:: ---------------------------------------------------------------------------
:: [3/7] Create & Activate Virtual Environment (.venv)
:: ---------------------------------------------------------------------------
if exist ".venv\Scripts\python.exe" goto :venv_exists

call :log "[3/7] Creating dedicated virtual environment .venv..."
%PYTHON_CMD% -m venv .venv >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail_venv
call :log "[3/7] Virtual environment created successfully."
goto :activate_venv

:fail_venv
call :log "[ERROR] Failed to create virtual environment .venv. See %LOG_FILE%."
goto :fail_pause

:venv_exists
call :log "[3/7] Virtual environment .venv already exists. Skipping creation."

:activate_venv
call :log "[3/7] Activating virtual environment..."
set "PATH=%~dp0.venv\Scripts;!PATH!"
goto :step_deps

:: ---------------------------------------------------------------------------
:: [4/7] Dependency Installation (PyTorch + requirements-lock.txt + CLIP)
:: ---------------------------------------------------------------------------
:step_deps
if exist ".venv\.deps_installed" goto :deps_already_installed

call :log "[4/7] Upgrading pip and setuptools..."
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools --prefer-binary >> "%LOG_FILE%" 2>&1

:: Check if PyTorch already exists
".venv\Scripts\python.exe" -c "import torch" >nul 2>&1
if not errorlevel 1 goto :torch_ready

where nvidia-smi >nul 2>&1
if errorlevel 1 goto :install_torch_cpu

call :log "[4/7] NVIDIA GPU detected via nvidia-smi. Installing PyTorch with CUDA acceleration..."
".venv\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124 --prefer-binary --retries 3 --timeout 30 >> "%LOG_FILE%" 2>&1
if not errorlevel 1 goto :torch_ready

call :log "[4/7] CUDA PyTorch install failed. Falling back to PyTorch CPU build..."

:install_torch_cpu
call :log "[4/7] Installing PyTorch CPU build..."
".venv\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --prefer-binary --retries 3 --timeout 30 >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :deps_failure

:torch_ready
call :log "[4/7] Installing pinned dependencies from requirements-lock.txt..."
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt --prefer-binary --retries 3 --timeout 30 >> "%LOG_FILE%" 2>&1
if not errorlevel 1 goto :install_clip

call :log "[4/7] Lockfile install encountered issues. Trying requirements.txt as fallback..."
".venv\Scripts\python.exe" -m pip install -r requirements.txt --prefer-binary --retries 3 --timeout 30 >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :deps_failure

:install_clip
call :log "[4/7] Installing OpenAI CLIP (pure zip download, zero Git requirement)..."
".venv\Scripts\python.exe" -m pip install --no-deps https://github.com/openai/CLIP/archive/master.zip >> "%LOG_FILE%" 2>&1
if not errorlevel 1 goto :deps_success

call :log "[4/7] Primary CLIP archive install failed. Installing openai-clip package..."
".venv\Scripts\python.exe" -m pip install openai-clip --prefer-binary >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :deps_failure

:deps_success
echo dependencies_installed > ".venv\.deps_installed"
call :log "[4/7] All dependencies installed successfully. Marker .venv\.deps_installed created."
goto :step_models

:deps_already_installed
call :log "[4/7] Dependency marker (.venv\.deps_installed) present. Skipping package installation."
goto :step_models

:deps_failure
call :log ""
call :log "========================================================================="
call :log " [ERROR] Dependency installation failed!"
call :log " Check your internet connection or see log details at: %LOG_FILE%"
call :log "========================================================================="
call :log ""
goto :fail_pause

:: ---------------------------------------------------------------------------
:: [5/7] Model Checkpoints Verification & Safe Download Fallbacks
:: ---------------------------------------------------------------------------
:step_models
call :log "[5/7] Verifying forensic model checkpoints..."

if not exist "ai_image_detection\models\clip" mkdir "ai_image_detection\models\clip" >nul 2>&1

:: Check if ViT-L-14.pt is in models\ or models\clip\
if not exist "ai_image_detection\models\clip\ViT-L-14.pt" if exist "ai_image_detection\models\ViT-L-14.pt" copy /y "ai_image_detection\models\ViT-L-14.pt" "ai_image_detection\models\clip\ViT-L-14.pt" >nul 2>&1
if not exist "ai_image_detection\models\ViT-L-14.pt" if exist "ai_image_detection\models\clip\ViT-L-14.pt" copy /y "ai_image_detection\models\clip\ViT-L-14.pt" "ai_image_detection\models\ViT-L-14.pt" >nul 2>&1

:: Verify ViT-L-14.pt existence and size (932,768,134 bytes)
set VIT_VALID=0
if exist "ai_image_detection\models\clip\ViT-L-14.pt" for %%F in ("ai_image_detection\models\clip\ViT-L-14.pt") do if %%~zF equ 932768134 set VIT_VALID=1

if "%VIT_VALID%"=="1" goto :vit_ok

call :log "[5/7] CLIP ViT-L/14 model checkpoint is missing. Downloading (~889 MB)..."
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$url = 'https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt'; " ^
    "$target = 'ai_image_detection\models\clip\ViT-L-14.pt'; " ^
    "try { " ^
    "  [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; " ^
    "  $wc = New-Object System.Net.WebClient; " ^
    "  $wc.DownloadFile($url, $target); " ^
    "} catch { exit 1 }" >> "%LOG_FILE%" 2>&1
if exist "ai_image_detection\models\clip\ViT-L-14.pt" (
    copy /y "ai_image_detection\models\clip\ViT-L-14.pt" "ai_image_detection\models\ViT-L-14.pt" >nul 2>&1
    set VIT_VALID=1
)

:vit_ok
:: Verify Linear Probe weights (4,083 bytes)
set PROBE_VALID=0
if exist "ai_image_detection\models\fc_weights.pth" for %%F in ("ai_image_detection\models\fc_weights.pth") do if %%~zF equ 4083 set PROBE_VALID=1

if "%PROBE_VALID%"=="1" goto :probe_ok

call :log "[5/7] Universal Fake Detect linear probe is missing. Downloading (~4 KB)..."
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$url = 'https://raw.githubusercontent.com/Yuheng-Li/UniversalFakeDetect/main/pretrained_weights/fc_weights.pth'; " ^
    "$target = 'ai_image_detection\models\fc_weights.pth'; " ^
    "try { " ^
    "  [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; " ^
    "  $wc = New-Object System.Net.WebClient; " ^
    "  $wc.DownloadFile($url, $target); " ^
    "} catch { exit 1 }" >> "%LOG_FILE%" 2>&1
if exist "ai_image_detection\models\fc_weights.pth" set PROBE_VALID=1

:probe_ok
if "%VIT_VALID%"=="1" if "%PROBE_VALID%"=="1" (
    call :log "[5/7] Model checkpoints verified: ViT-L-14.pt and fc_weights.pth ready."
    goto :models_verified
)

if "%VIT_VALID%" neq "1" (
    call :log "[WARNING] CLIP ViT-L-14 checkpoint could not be downloaded."
    call :log "  Place ViT-L-14.pt in ai_image_detection\models\clip"
)
if "%PROBE_VALID%" neq "1" (
    call :log "[WARNING] Linear probe weights could not be automatically downloaded."
    call :log "  Place fc_weights.pth in ai_image_detection\models"
)

:models_verified

:: ---------------------------------------------------------------------------
:: [6/7] Ensure Required Storage Directories Exist
:: ---------------------------------------------------------------------------
call :log "[6/7] Ensuring local evidence folders exist..."
if not exist "uploads" mkdir "uploads"
if not exist "artifacts\ai_image_detection" mkdir "artifacts\ai_image_detection"
if not exist "ai_image_detection\cache" mkdir "ai_image_detection\cache"
if not exist "ai_image_detection\models\clip" mkdir "ai_image_detection\models\clip"
call :log "[6/7] Storage directories initialized."

:: ---------------------------------------------------------------------------
:: [7/7] Free Port Selection & Server Launch
:: ---------------------------------------------------------------------------
call :log "[7/7] Selecting available server port..."
set PORT=%DEFAULT_PORT%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p = 8000; " ^
    "while ($p -le 8100) { " ^
    "  try { " ^
    "    $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Parse('127.0.0.1'), $p); " ^
    "    $l.Start(); " ^
    "    $l.Stop(); " ^
    "    Write-Output $p; " ^
    "    break; " ^
    "  } catch { $p++ } " ^
    "}" > "%TEMP%\ps05_port.tmp" 2>nul
if exist "%TEMP%\ps05_port.tmp" (
    set /p PORT=<"%TEMP%\ps05_port.tmp"
    del /f /q "%TEMP%\ps05_port.tmp" >nul 2>&1
)
call :log "[7/7] Assigned server port: !PORT!"

:: Enforce 100% Offline Mode for ML Inference at runtime
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

call :log ""
call :log "=============================================="
call :log " %APP_NAME% is running"
call :log " Open this link in your browser:"
call :log " http://127.0.0.1:!PORT!/"
call :log " Press CTRL+C to stop the server"
call :log "=============================================="
call :log ""

:: Launch browser automatically after a short 2-second background delay
start "" cmd /c "ping 127.0.0.1 -n 3 >nul & start http://127.0.0.1:!PORT!/"

:: Foreground Server Process using .venv python
".venv\Scripts\python.exe" -m uvicorn %APP_MODULE% --host 127.0.0.1 --port !PORT!
if errorlevel 1 (
    call :log "[ERROR] Web server terminated with error code: %errorlevel%"
    goto :fail_pause
)
goto :end_exit


:: ===========================================================================
:: DRYRUN SIMULATION ROUTINE (/dryrun)
:: ===========================================================================
:execute_dryrun
echo [DRYRUN] Simulating complete provisioning sequence without modifying system...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; " ^
    "$is64 = [Environment]::Is64BitOperatingSystem; " ^
    "$curDrive = (Get-Item .).Root.Name; " ^
    "$driveLetter = $curDrive.TrimEnd(':\'); " ^
    "$freeBytes = (Get-PSDrive $driveLetter).Free; " ^
    "$freeGB = [math]::Round(($freeBytes / 1GB), 2); " ^
    "Write-Host ('[1/7] [DRYRUN] System Architecture : ' + $(if ($is64) { '64-bit Windows [Supported]' } else { '32-bit [Unsupported]' })); " ^
    "Write-Host ('[1/7] [DRYRUN] Free Disk Space     : ' + $freeGB + ' GB on drive ' + $curDrive + $(if ($freeGB -ge 10) { ' [OK]' } else { ' [WARNING: Low space]' })); " ^
    "$vc = (Test-Path 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') -or (Test-Path ($env:SystemRoot + '\System32\vcruntime140.dll')); " ^
    "Write-Host ('[2/7] [DRYRUN] VC++ Redistributable: ' + $(if ($vc) { 'Present [No install needed]' } else { 'Missing - Would install Microsoft.VCRedist.2015+.x64 via winget' })); " ^
    "$py = Get-Command py -ErrorAction SilentlyContinue; " ^
    "$p310 = if ($py) { & py -V:3.10 -c 'import sys; print(sys.version.split()[0])' 2>$null } else { $null }; " ^
    "Write-Host ('[2/7] [DRYRUN] Python 3.10         : ' + $(if ($p310) { 'Found via py launcher (' + $p310 + ') [No install needed]' } else { 'Missing - Would auto-install Python.Python.3.10 via winget' })); " ^
    "Write-Host '[2/7] [DRYRUN] Git Requirement     : None (CLIP installed via zip archive)'; " ^
    "Write-Host '[2/7] [DRYRUN] FFmpeg Requirement  : None (image forensic module only)'; " ^
    "Write-Host '[2/7] [DRYRUN] Node.js Requirement : None (vanilla HTML/JS frontend)'; " ^
    "$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue; " ^
    "Write-Host '[3/7] [DRYRUN] Virtual Environment : Would create .venv using Python 3.10'; " ^
    "Write-Host ('[4/7] [DRYRUN] PyTorch Selection    : ' + $(if ($smi) { 'NVIDIA GPU detected - Would install CUDA build (cu124)' } else { 'No GPU - Would install PyTorch CPU build' })); " ^
    "Write-Host '[4/7] [DRYRUN] Dependencies       : Would install pinned packages from requirements-lock.txt and CLIP master.zip'; " ^
    "$vit = 'ai_image_detection\models\clip\ViT-L-14.pt'; " ^
    "if (-not (Test-Path $vit)) { $vit = 'ai_image_detection\models\ViT-L-14.pt' }; " ^
    "$vitOk = (Test-Path $vit) -and ((Get-Item $vit).Length -eq 932768134); " ^
    "Write-Host ('[5/7] [DRYRUN] ViT-L-14.pt Checkpoint: ' + $(if ($vitOk) { 'Found (932,768,134 bytes) [Skip download]' } else { 'Missing - Would download 889.5 MB from Azure CDN' })); " ^
    "$probe = 'ai_image_detection\models\fc_weights.pth'; " ^
    "$probeOk = (Test-Path $probe) -and ((Get-Item $probe).Length -eq 4083); " ^
    "Write-Host ('[5/7] [DRYRUN] fc_weights.pth Probe  : ' + $(if ($probeOk) { 'Found (4,083 bytes) [Skip download]' } else { 'Missing - Would download 4 KB from GitHub Raw' })); "

echo [6/7] [DRYRUN] Directory Setup     : Would ensure uploads, artifacts\ai_image_detection, cache, logs
echo [7/7] [DRYRUN] Server Launch       : Would scan free port from 8000 upwards and launch uvicorn main_standalone:app
echo.
echo =========================================================================
echo  [DRYRUN COMPLETE] Simulation finished successfully. Zero changes made.
echo =========================================================================
if "!NO_PAUSE!"=="0" pause
exit /b 0

:: ---------------------------------------------------------------------------
:: Helper: Logger subroutine
:: ---------------------------------------------------------------------------
:log
echo %~1
if defined LOG_FILE echo [%date% %time%] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:fail_pause
call :log ""
call :log "Setup could not complete. Review log details at: %LOG_FILE%"
if "!NO_PAUSE!"=="0" pause
exit /b 1

:end_exit
exit /b 0
