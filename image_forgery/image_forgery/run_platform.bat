@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

title PS-05 Image Forgery Forensic Platform

:: Default flags
set "DRYRUN=0"
set "RESET=0"
set "FORCE_CPU=0"
set "EXTRA_ARGS="

:: Parse command line arguments using shift /1 so SCRIPT_DIR and %0 are preserved
:parse_args
if "%~1"=="" goto after_args
if /i "%~1"=="/dryrun" (
    set "DRYRUN=1"
    shift /1
    goto parse_args
)
if /i "%~1"=="--dry-run" (
    set "DRYRUN=1"
    shift /1
    goto parse_args
)
if /i "%~1"=="/reset" (
    set "RESET=1"
    shift /1
    goto parse_args
)
if /i "%~1"=="--reset" (
    set "RESET=1"
    shift /1
    goto parse_args
)
if /i "%~1"=="--cpu" (
    set "FORCE_CPU=1"
    shift /1
    goto parse_args
)
set "EXTRA_ARGS=!EXTRA_ARGS! %1"
shift /1
goto parse_args
:after_args

:: Initialize logging directory and timestamped log file
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"
for /f "usebackq tokens=*" %%D in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')" 2^>nul`) do set "LOG_TS=%%D"
if not defined LOG_TS set "LOG_TS=latest"
set "SETUP_LOG=%SCRIPT_DIR%logs\setup_%LOG_TS%.txt"

echo ==============================================================================
echo       PS-05 Image Forgery Forensic Platform - Launcher
echo ==============================================================================
echo [Log] Recording diagnostic and setup trace to:
echo       %SETUP_LOG%
echo.

echo [Log Session: %LOG_TS%] > "%SETUP_LOG%"
echo [Script Directory: %SCRIPT_DIR%] >> "%SETUP_LOG%"

:: Reset flag handling
if "%RESET%"=="1" (
    echo [Reset] Full reset requested. Removing existing environment and cache markers...
    if exist "%SCRIPT_DIR%.deps_installed" del /f /q "%SCRIPT_DIR%.deps_installed" >nul 2>&1
    if exist "%SCRIPT_DIR%.setup_ok" del /f /q "%SCRIPT_DIR%.setup_ok" >nul 2>&1
    if exist "%SCRIPT_DIR%.venv" (
        echo [Reset] Purging virtual environment .venv...
        rmdir /s /q "%SCRIPT_DIR%.venv" >nul 2>&1
    )
    echo [Reset] Clean slate prepared.
    echo.
)

:: Step 1: Hardware Architecture Check
echo [1/6] Verifying Hardware Architecture...
echo [1/6] Checking Hardware Architecture... >> "%SETUP_LOG%"
if not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    echo [ERROR] 64-bit AMD64 architecture is strictly required.
    echo Detected architecture: %PROCESSOR_ARCHITECTURE%
    echo [ERROR] 64-bit AMD64 required. Detected: %PROCESSOR_ARCHITECTURE% >> "%SETUP_LOG%"
    pause
    exit /b 1
)
echo   - Architecture: 64-bit AMD64 [PASS]
echo   - Architecture: 64-bit AMD64 [PASS] >> "%SETUP_LOG%"

:: Step 2: Disk Space Check
echo.
echo [2/6] Verifying Available Disk Space...
powershell -NoProfile -Command "$f = [System.IO.DriveInfo]::new((Get-Location).Drive.Name).AvailableFreeSpace / 1GB; if ($f -lt 3.0) { exit 2 } elseif ($f -lt 10.0) { exit 1 } else { exit 0 }" >nul 2>&1
set "DISK_STATUS=%ERRORLEVEL%"
if "%DISK_STATUS%"=="2" (
    echo [ERROR] Less than 3 GB free disk space available on drive %~d0.
    echo At least 3 GB is required for libraries and checkpoints.
    echo [ERROR] Disk space under 3 GB. Cannot proceed. >> "%SETUP_LOG%"
    pause
    exit /b 1
)
if "%DISK_STATUS%"=="1" (
    echo   - Disk Space: [WARNING] Under 10 GB free. Setup will continue, but 10 GB is recommended.
    echo   - Disk Space: Warning under 10 GB free >> "%SETUP_LOG%"
) else (
    echo   - Disk Space: Sufficient [PASS]
    echo   - Disk Space: Sufficient [PASS] >> "%SETUP_LOG%"
)

:: Step 3: Operating System Version Check
echo.
echo [3/6] Verifying Windows Build...
powershell -NoProfile -Command "$b = [System.Environment]::OSVersion.Version.Build; if ($b -ge 19041) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo   - Windows Version: [WARNING] OS build is below 19041 - Windows 10 version 2004. Python 3.10+ may be unstable.
    echo   - Windows Version: Warning OS build below 19041 >> "%SETUP_LOG%"
) else (
    echo   - Windows Version: Windows 10 or 11 build 19041+ [PASS]
    echo   - Windows Version: Windows 10 or 11 build 19041+ [PASS] >> "%SETUP_LOG%"
)

:: Step 4: Visual C++ Runtime Check
echo.
echo [4/6] Verifying Visual C++ Runtime...
if not exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo   - Visual C++ Runtime vcruntime140.dll: MISSING
    echo   - Visual C++ Runtime: MISSING >> "%SETUP_LOG%"
    if "%DRYRUN%"=="1" (
        echo [DRY-RUN FAIL] Visual C++ Redistributable 2015-2022 is required.
    ) else (
        echo [Setup] Attempting automated installation via winget...
        where winget.exe >nul 2>&1
        if not errorlevel 1 (
            winget install --id Microsoft.VCRedist.2015+.x64 -e --source winget --silent --accept-package-agreements --accept-source-agreements >> "%SETUP_LOG%" 2>&1
            if exist "%SystemRoot%\System32\vcruntime140.dll" (
                echo   - Visual C++ Runtime: Successfully installed [PASS]
            ) else (
                echo [ERROR] Installation failed. Please install manually:
                echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
                pause
                exit /b 1
            )
        ) else (
            echo [ERROR] Visual C++ Redistributable is required.
            echo Download and run the official installer:
            echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
            pause
            exit /b 1
        )
    )
) else (
    echo   - Visual C++ Runtime: Installed [vcruntime140.dll found] [PASS]
    echo   - Visual C++ Runtime: Installed [PASS] >> "%SETUP_LOG%"
)

:: Step 5: Locate or Provision Python 3.10 - 3.13
echo.
echo [5/6] Verifying Python Environment [Python 3.10 to 3.13]...
set "PYTHON_BIN="

:: Check py launcher
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYTHON_BIN (
        py -%%V -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_BIN=py -%%V"
    )
)

if not defined PYTHON_BIN (
    py -3 -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_BIN=py -3"
)

:: Check python in PATH
if not defined PYTHON_BIN (
    python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_BIN=python"
)

:: Check AppData Programs directories
if not defined PYTHON_BIN (
    for %%V in (313 312 311 310) do (
        if not defined PYTHON_BIN (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_BIN=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )
)

:: Check ProgramFiles directories
if not defined PYTHON_BIN (
    for %%V in (313 312 311 310) do (
        if not defined PYTHON_BIN (
            if exist "%ProgramFiles%\Python%%V\python.exe" (
                "%ProgramFiles%\Python%%V\python.exe" -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_BIN=%ProgramFiles%\Python%%V\python.exe"
            )
        )
    )
)

:: Provision Python via winget if missing
if not defined PYTHON_BIN (
    echo   - Python: NOT FOUND
    if "%DRYRUN%"=="1" (
        echo [DRY-RUN FAIL] Python 3.10-3.13 is missing.
    ) else (
        echo [Setup] Attempting to install Python 3.10 via winget...
        where winget.exe >nul 2>&1
        if not errorlevel 1 (
            winget install --id Python.Python.3.10 -e --source winget --silent --accept-package-agreements --accept-source-agreements >> "%SETUP_LOG%" 2>&1
            
            :: Refresh PATH for current session
            for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')" 2^>nul`) do set "PATH=%%P;!PATH!"

            if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
                set "PYTHON_BIN=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
            ) else if exist "%ProgramFiles%\Python310\python.exe" (
                set "PYTHON_BIN=%ProgramFiles%\Python310\python.exe"
            ) else (
                py -3.10 -c "import sys; sys.exit(0)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_BIN=py -3.10"
            )
        )
    )
)

if not defined PYTHON_BIN (
    if "%DRYRUN%"=="1" (
        echo [DRY-RUN] Aborting audit due to missing Python runtime.
        pause
        exit /b 1
    )
    echo.
    echo ==============================================================================
    echo [ERROR] Python 3.10 or newer was not detected on this system.
    echo.
    echo Automated installation via winget was unavailable or did not complete.
    echo Please install Python manually:
    echo   Direct Download: https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
    echo   IMPORTANT: In the installer window, check the box:
    echo              [X] Add python.exe to PATH
    echo ==============================================================================
    echo.
    pause
    exit /b 1
)

echo   - Python: Found %PYTHON_BIN% [PASS]
echo   - Python: %PYTHON_BIN% [PASS] >> "%SETUP_LOG%"

:: Step 6: Virtual Environment, Dependencies & Models
echo.
echo [6/6] Verifying Virtual Environment and Dependencies...

:: Check virtual environment integrity
if exist "%SCRIPT_DIR%.venv" (
    if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
        echo [Setup] Corrupted virtual environment detected. Recreating .venv...
        rmdir /s /q "%SCRIPT_DIR%.venv" >nul 2>&1
    )
)

if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    if "%DRYRUN%"=="1" (
        echo   - Virtual Environment: .venv missing [NEEDS PROVISIONING]
    ) else (
        echo [Setup] Creating virtual environment .venv...
        if "%PYTHON_BIN%"=="py -3" (
            py -3 -m venv "%SCRIPT_DIR%.venv" >> "%SETUP_LOG%" 2>&1
        ) else if "%PYTHON_BIN:~0,4%"=="py -" (
            %PYTHON_BIN% -m venv "%SCRIPT_DIR%.venv" >> "%SETUP_LOG%" 2>&1
        ) else if "%PYTHON_BIN%"=="python" (
            python -m venv "%SCRIPT_DIR%.venv" >> "%SETUP_LOG%" 2>&1
        ) else (
            "%PYTHON_BIN%" -m venv "%SCRIPT_DIR%.venv" >> "%SETUP_LOG%" 2>&1
        )
        if errorlevel 1 (
            echo [ERROR] Virtual environment creation failed. Check logs at %SETUP_LOG%
            pause
            exit /b 1
        )
    )
)

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "APP_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    set "APP_PYTHON=%PYTHON_BIN%"
)

:: Check if dependencies need installation
set "NEEDS_DEPS=1"
set "LOCK_FILE=%SCRIPT_DIR%requirements-lock.txt"
set "MARKER_FILE=%SCRIPT_DIR%.deps_installed"

if exist "%MARKER_FILE%" (
    "%APP_PYTHON%" -c "import hashlib, sys; sys.exit(0 if open(r'%MARKER_FILE%').read().strip() == hashlib.sha256(open(r'%LOCK_FILE%','rb').read()).hexdigest() else 1)" >nul 2>&1
    if not errorlevel 1 set "NEEDS_DEPS=0"
)

if "%NEEDS_DEPS%"=="1" (
    if "%DRYRUN%"=="1" (
        echo   - Dependencies: Not installed or lockfile changed [NEEDS INSTALLATION]
    ) else (
        echo.
        echo ==============================================================================
        echo   Installing Locked Forensic Dependencies - Please Wait
        echo   Logging full output to: %SETUP_LOG%
        echo ==============================================================================
        
        echo [1/4] Upgrading pip, setuptools, and wheel...
        "%APP_PYTHON%" -m pip install --upgrade pip setuptools wheel >> "%SETUP_LOG%" 2>&1

        echo [2/4] Detecting GPU accelerator for PyTorch...
        set "HAS_CUDA=0"
        where nvidia-smi.exe >nul 2>&1
        if not errorlevel 1 (
            if not "%FORCE_CPU%"=="1" set "HAS_CUDA=1"
        )

        if "%HAS_CUDA%"=="1" (
            echo   - NVIDIA GPU detected. Installing PyTorch with CUDA 12.8 index...
            "%APP_PYTHON%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --prefer-binary --retries 5 --timeout 60 >> "%SETUP_LOG%" 2>&1
            if errorlevel 1 (
                echo   - [Warning] CUDA PyTorch install failed. Falling back to CPU PyTorch...
                "%APP_PYTHON%" -m pip install torch torchvision --prefer-binary --retries 5 --timeout 60 >> "%SETUP_LOG%" 2>&1
            )
        ) else (
            echo   - Installing PyTorch in CPU mode...
            "%APP_PYTHON%" -m pip install torch torchvision --prefer-binary --retries 5 --timeout 60 >> "%SETUP_LOG%" 2>&1
        )

        echo [3/4] Installing platform requirements from requirements-lock.txt...
        "%APP_PYTHON%" -m pip install -r "%LOCK_FILE%" --prefer-binary --retries 5 --timeout 60 >> "%SETUP_LOG%" 2>&1
        if errorlevel 1 (
            echo [ERROR] Dependency installation failed. Inspect %SETUP_LOG% for details.
            pause
            exit /b 1
        )

        echo [4/4] Writing installation marker file .deps_installed...
        "%APP_PYTHON%" -c "import hashlib; open(r'%MARKER_FILE%','w').write(hashlib.sha256(open(r'%LOCK_FILE%','rb').read()).hexdigest())" >nul 2>&1
        echo   - Dependencies installed successfully [PASS]
    )
) else (
    echo   - Dependencies: Verified via .deps_installed [PASS]
    echo   - Dependencies: Verified [PASS] >> "%SETUP_LOG%"
)

:: Step 7: Check or Download Model Weights
echo.
echo [Check] Verifying TruFor Model Weights...
"%APP_PYTHON%" launch.py --check-weights >nul 2>&1
if errorlevel 1 (
    if "%DRYRUN%"=="1" (
        echo   - TruFor Checkpoint [trufor.pth.tar]: MISSING or CHECKSUM MISMATCH [NEEDS DOWNLOAD]
    ) else (
        echo   - TruFor Checkpoint: Missing or incomplete. Starting automated download...
        "%APP_PYTHON%" launch.py --download-weights
        if errorlevel 1 (
            echo [ERROR] Model download failed. Check manual instructions above.
            pause
            exit /b 1
        )
    )
) else (
    echo   - TruFor Checkpoint: Verified [281.5 MB, SHA-256 match] [PASS]
    echo   - TruFor Checkpoint: Verified [PASS] >> "%SETUP_LOG%"
)

:: Dry-Run Audit Finalization
if "%DRYRUN%"=="1" (
    echo.
    echo ==============================================================================
    echo                           DRY-RUN AUDIT SUMMARY
    echo ==============================================================================
    "%APP_PYTHON%" launch.py --dry-run
    set "DRY_RES=!ERRORLEVEL!"
    if "!DRY_RES!"=="0" (
        echo.
        echo [PASS] All system prerequisites and assets are READY to run on this machine!
        exit /b 0
    ) else (
        echo.
        echo [FAIL] System audit detected missing requirements. Review output above.
        exit /b 1
    )
)

:: Launch the Application
echo.
echo ==============================================================================
echo   Starting PS-05 Image Forgery Forensic Application
echo ==============================================================================
"%APP_PYTHON%" launch.py !EXTRA_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo ==============================================================================
    echo [ERROR] Application terminated with exit code %EXIT_CODE%.
    echo Trace details logged to: %SETUP_LOG%
    echo ==============================================================================
    pause
)
