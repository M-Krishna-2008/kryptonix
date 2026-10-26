@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title PS-05 Forensic Platform - System Diagnostics

echo ==============================================================================
echo        PS-05 Image Forgery Forensic Platform - System Diagnostic Tool
echo ==============================================================================
echo.

:: 1. Operating System & Architecture
echo [1/5] Checking Operating System & Hardware Architecture...
for /f "tokens=4-5 delims=[.] " %%i in ('ver') do set "WIN_VER=%%i.%%j"
echo   - Windows Version:         %WIN_VER%
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo   - Architecture:            64-bit (AMD64) [OK]
) else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    echo   - Architecture:            64-bit (WOW64) [OK]
) else (
    echo   - Architecture:            %PROCESSOR_ARCHITECTURE% [WARNING: 64-bit OS required]
)

:: 2. Disk Space
echo.
echo [2/5] Checking Disk Space...
for /f "usebackq tokens=*" %%S in (`powershell -NoProfile -Command "[math]::Round(([System.IO.DriveInfo]::new((Get-Location).Drive.Name).AvailableFreeSpace / 1GB), 1)" 2^>nul`) do set "FREE_GB=%%S"
if defined FREE_GB (
    echo   - Available Disk Space:    %FREE_GB% GB
    powershell -NoProfile -Command "if ([double]'%FREE_GB%' -lt 10.0) { exit 1 } else { exit 0 }" >nul 2>&1
    if errorlevel 1 (
        echo     [WARNING] Free disk space is under 10 GB. 10 GB recommended for deep models and dependencies.
    ) else (
        echo     [OK] Disk space is sufficient.
    )
) else (
    echo   - Available Disk Space:    Unknown
)

:: 3. Required & Optional System Tools
echo.
echo [3/5] Checking System Tools & Runtimes...

:: Winget
where winget.exe >nul 2>&1
if not errorlevel 1 (
    echo   - Windows Package Manager (winget): Installed [OK]
) else (
    echo   - Windows Package Manager (winget): NOT FOUND [Manual installer fallback active]
)

:: Python
set "FOUND_PY="
py -3 -c "import sys; print(sys.version.split()[0])" >.pyver.tmp 2>nul
if not errorlevel 1 (
    set /p PY_V=<.pyver.tmp
    set "FOUND_PY=py -3 (v!PY_V!)"
)
if exist .pyver.tmp del /f /q .pyver.tmp >nul 2>&1

if not defined FOUND_PY (
    python -c "import sys; print(sys.version.split()[0])" >.pyver.tmp 2>nul
    if not errorlevel 1 (
        set /p PY_V=<.pyver.tmp
        set "FOUND_PY=python in PATH (v!PY_V!)"
    )
    if exist .pyver.tmp del /f /q .pyver.tmp >nul 2>&1
)

if not defined FOUND_PY (
    for %%V in (314 313 312 311 310) do (
        if not defined FOUND_PY (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys; print(sys.version.split()[0])" >.pyver.tmp 2>nul
                if not errorlevel 1 (
                    set /p PY_V=<.pyver.tmp
                    set "FOUND_PY=%%LOCALAPPDATA%%\Programs\Python\Python%%V (v!PY_V!)"
                )
                if exist .pyver.tmp del /f /q .pyver.tmp >nul 2>&1
            )
        )
    )
)

if defined FOUND_PY (
    echo   - Python:                  Found: %FOUND_PY% [OK]
) else (
    echo   - Python (3.10+):          NOT FOUND [Will be installed via winget or manual download]
)

:: Visual C++ Redistributable
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo   - Visual C++ Runtime:      Installed (vcruntime140.dll found) [OK]
) else (
    echo   - Visual C++ Runtime:      NOT FOUND [Required by PyTorch - will be installed]
)

:: NVIDIA GPU & CUDA
where nvidia-smi.exe >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%G in ('powershell -NoProfile -Command "(Get-Command nvidia-smi.exe).Source" 2^>nul') do set "SMI_PATH=%%G"
    echo   - NVIDIA GPU (nvidia-smi): Detected [CUDA acceleration enabled]
) else (
    echo   - NVIDIA GPU (nvidia-smi): Not detected [CPU fallback mode will be used]
)

:: Git, FFmpeg, Node.js (Informational)
where git.exe >nul 2>&1
if not errorlevel 1 (
    echo   - Git:                     Installed (optional, not required)
) else (
    echo   - Git:                     Not installed (not required for image forensics)
)

where ffmpeg.exe >nul 2>&1
if not errorlevel 1 (
    echo   - FFmpeg:                  Installed (optional, not required)
) else (
    echo   - FFmpeg:                  Not installed (not required for still image module)
)

where node.exe >nul 2>&1
if not errorlevel 1 (
    echo   - Node.js:                 Installed (optional, not required)
) else (
    echo   - Node.js:                 Not installed (not required - UI is plain HTML/CSS/JS)
)

:: 4. Network Reachability
echo.
echo [4/5] Checking Network Reachability...

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'https://pypi.org' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo   - Python Package Index (PyPI):   Reachable [OK]
) else (
    echo   - Python Package Index (PyPI):   UNREACHABLE [Offline mode or firewall]
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'https://huggingface.co' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo   - Model Mirror (Hugging Face):   Reachable [OK]
) else (
    echo   - Model Mirror (Hugging Face):   UNREACHABLE [Offline mode or firewall]
)

:: 5. Model Weights Check
echo.
echo [5/5] Checking Forensic Model Checkpoints...
set "MODEL_FILE=%~dp0models\trufor\trufor.pth.tar"
if exist "%MODEL_FILE%" (
    for /f "usebackq tokens=*" %%B in (`powershell -NoProfile -Command "[math]::Round(((Get-Item '%MODEL_FILE%').Length / 1MB), 2)" 2^>nul`) do set "MODEL_MB=%%B"
    echo   - TruFor Checkpoint (trufor.pth.tar): PRESENT (!MODEL_MB! MB) [OK]
) else (
    echo   - TruFor Checkpoint (trufor.pth.tar): MISSING [Will be downloaded automatically by launcher]
)

echo.
echo ==============================================================================
echo Diagnostic completed. Press any key to exit.
echo ==============================================================================
pause >nul
