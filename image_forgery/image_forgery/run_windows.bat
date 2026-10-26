@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title PS-05: Image Forgery Forensic Platform

set "SETUP_LOG=%~dp0setup.log"
set "MARKER_FILE=%~dp0.venv\.setup_ok"
set "REQ_FILE=%~dp0requirements.txt"
set "FORCE_CPU=0"
set "REINSTALL=0"

:: Parse command line arguments
for %%A in (%*) do (
    if "%%A"=="--cpu" set "FORCE_CPU=1"
    if "%%A"=="--reinstall" set "REINSTALL=1"
)

if "%REINSTALL%"=="1" (
    if exist "%MARKER_FILE%" del /f /q "%MARKER_FILE%" >nul 2>&1
    echo [Setup] Reinstall requested. Cache marker removed.
)

:: Locate Python 3.10+
set "PYTHON_BIN="

:: 1. Search common Windows user install directories (%LOCALAPPDATA%\Programs\Python)
for %%V in (314 313 312 311 310) do (
    if not defined PYTHON_BIN (
        if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "PYTHON_BIN=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        )
    )
)

:: 2. Search common 64-bit Program Files install directories
if not defined PYTHON_BIN (
    for %%V in (314 313 312 311 310) do (
        if not defined PYTHON_BIN (
            if exist "%ProgramFiles%\Python%%V\python.exe" (
                "%ProgramFiles%\Python%%V\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_BIN=%ProgramFiles%\Python%%V\python.exe"
            )
        )
    )
)

:: 3. Try py -3 launcher
if not defined PYTHON_BIN (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_BIN=py -3"
)

:: 4. Try python in PATH (skipping broken WindowsApps alias if it fails)
if not defined PYTHON_BIN (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_BIN=python"
)

:: 5. Try C:\Python* root directories
if not defined PYTHON_BIN (
    for %%V in (314 313 312 311 310) do (
        if not defined PYTHON_BIN (
            if exist "C:\Python%%V\python.exe" (
                "C:\Python%%V\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
                if not errorlevel 1 set "PYTHON_BIN=C:\Python%%V\python.exe"
            )
        )
    )
)

if not defined PYTHON_BIN (
    echo.
    echo ==============================================================================
    echo [ERROR] Python 3.10 or newer was not detected on this system.
    echo.
    echo 1. Download and install Python from: https://www.python.org/downloads/
    echo 2. During installation, ensure you check the box: 'Add Python to PATH'
    echo ==============================================================================
    echo.
    pause
    exit /b 1
)

:: Prepare executable command string
if "%PYTHON_BIN%"=="py -3" (
    set "RUN_PY=py -3"
) else if "%PYTHON_BIN%"=="python" (
    set "RUN_PY=python"
) else (
    set RUN_PY="%PYTHON_BIN%"
)

echo [System] Found Python: %PYTHON_BIN%

:: Create virtual environment if absent
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment .venv...
    %RUN_PY% -m venv --system-site-packages .venv >> "%SETUP_LOG%" 2>&1
    if errorlevel 1 (
        echo [Warning] Virtual environment creation failed. Falling back to host Python.
        set "APP_PYTHON=%PYTHON_BIN%"
    ) else (
        set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
    )
) else (
    set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
)

:: Check if setup has already been completed for current requirements.txt
set "NEEDS_SETUP=1"
if exist "%MARKER_FILE%" (
    "%APP_PYTHON%" -c "import hashlib, sys; h1 = open(r'%MARKER_FILE%').read().strip(); h2 = hashlib.sha256(open(r'%REQ_FILE%','rb').read()).hexdigest(); sys.exit(0 if h1 == h2 else 1)" >nul 2>&1
    if not errorlevel 1 set "NEEDS_SETUP=0"
)

if "%NEEDS_SETUP%"=="1" (
    echo.
    echo ==============================================================================
    echo   First-Run Forensic Module Setup - Logging to setup.log
    echo ==============================================================================
    echo. > "%SETUP_LOG%"

    echo [1/4] Verifying pip tooling...
    "%APP_PYTHON%" -m pip install --upgrade pip >> "%SETUP_LOG%" 2>&1

    :: Detect GPU
    set "HAS_NVIDIA=0"
    where nvidia-smi.exe >nul 2>&1
    if not errorlevel 1 set "HAS_NVIDIA=1"

    if "%FORCE_CPU%"=="1" (
        echo [2/4] Installing PyTorch in CPU mode as requested...
        "%APP_PYTHON%" -m pip install torch torchvision >> "%SETUP_LOG%" 2>&1
    ) else if "%HAS_NVIDIA%"=="1" (
        echo [2/4] NVIDIA GPU detected. Installing PyTorch with CUDA 12.8 support...
        "%APP_PYTHON%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 >> "%SETUP_LOG%" 2>&1
    ) else (
        echo [2/4] No NVIDIA GPU detected. Installing PyTorch in CPU mode...
        "%APP_PYTHON%" -m pip install torch torchvision >> "%SETUP_LOG%" 2>&1
    )

    echo [3/4] Installing forensic platform requirements...
    "%APP_PYTHON%" -m pip install -r "%REQ_FILE%" >> "%SETUP_LOG%" 2>&1

    :: Write verification marker file
    if not exist "%~dp0.venv" mkdir "%~dp0.venv"
    "%APP_PYTHON%" -c "import hashlib; open(r'%MARKER_FILE%','w').write(hashlib.sha256(open(r'%REQ_FILE%','rb').read()).hexdigest())" >nul 2>&1
    echo [4/4] Environment setup complete.
    echo.
)

:: Launch the application
echo [Launch] Starting forensic application...
"%APP_PYTHON%" launch.py %*
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    echo Check setup.log or console output above.
    echo ==============================================================================
    pause
)
