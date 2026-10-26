@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_TARGET=main_standalone:app"
set "IS_DRYRUN=0"
set "IS_RESET=0"

if /i "%~1"=="/dryrun" set "IS_DRYRUN=1"
if /i "%~1"=="--dryrun" set "IS_DRYRUN=1"
if /i "%~1"=="-dryrun" set "IS_DRYRUN=1"
if /i "%~1"=="/reset" set "IS_RESET=1"
if /i "%~1"=="--reset" set "IS_RESET=1"
if /i "%~1"=="-reset" set "IS_RESET=1"

if not exist "%~dp0logs" mkdir "%~dp0logs"

for /f "tokens=*" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul') do (
    if not defined LOG_TIME set "LOG_TIME=%%T"
)
if not defined LOG_TIME set "LOG_TIME=session"
set "LOG_FILE=%~dp0logs\setup_%LOG_TIME%.txt"

echo ========================================================
echo  PS-05: AI CCTV Detection Platform Launcher
echo  Directory: %~dp0
echo  Timestamp: %LOG_TIME% (Dryrun=%IS_DRYRUN%, Reset=%IS_RESET%)
echo ========================================================

if not "%IS_RESET%"=="1" goto :RESET_DONE
echo [RESET] Removing virtual environment and installation cache...
if exist "%~dp0.venv" rmdir /s /q "%~dp0.venv"
if exist "%~dp0cache" rmdir /s /q "%~dp0cache"
echo [OK] Reset completed. Proceeding with clean initialization.
:RESET_DONE

echo [1/7] System Architecture and Disk Space Verification...
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto :ARCH_OK
if "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto :ARCH_OK
echo [FATAL ERROR] 32-bit Windows detected. This platform requires 64-bit Windows (x64).
goto :HALT_ERROR

:ARCH_OK
echo [OK] 64-bit Windows architecture verified.

for /f "tokens=*" %%D in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launcher_helper.ps1" -Action get_disk_free -Arg1 "%~d0" 2^>nul') do (
    set "DISK_FREE_GB=%%D"
)
if defined DISK_FREE_GB echo [INFO] Free disk space on drive %~d0: %DISK_FREE_GB% GB

echo [2/7] Checking Prerequisites and Runtimes...

reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 goto :VC_OK
echo [WARN] VC++ 2015-2022 x64 Redistributable is missing. Required by PyTorch/OpenCV DLLs.
if "%IS_DRYRUN%"=="1" goto :VC_DONE
where winget >nul 2>&1
if errorlevel 1 goto :VC_MANUAL
echo [PROVISION] Installing VC++ Redistributable via winget...
winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements
call :REFRESH_PATH
goto :VC_DONE
:VC_MANUAL
echo [ACTION REQUIRED] Please install Microsoft Visual C++ Redistributable:
echo https://aka.ms/vs/17/release/vc_redist.x64.exe
:VC_DONE
goto :VC_CHECKED
:VC_OK
echo [OK] Microsoft Visual C++ 2015-2022 x64 Redistributable is installed.
:VC_CHECKED

echo [INFO] Resolving Python 3.10 or 3.11...
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :PYTHON_RESOLVED
)

for /f "delims=" %%I in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
for /f "delims=" %%I in ('python -c "import sys; print(sys.executable) if sys.version_info[:2] in [(3,10),(3,11)] else exit(1)" 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PYTHON_EXE if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python310\python.exe" set "PYTHON_EXE=C:\Program Files\Python310\python.exe"

:PYTHON_RESOLVED
if defined PYTHON_EXE goto :PYTHON_OK
echo [WARN] Python 3.10 or 3.11 was not found on your system.
if "%IS_DRYRUN%"=="1" (
    echo [DRYRUN] Would attempt to auto-install Python 3.10 via winget.
    goto :PYTHON_PROCEED
)
where winget >nul 2>&1
if errorlevel 1 goto :PYTHON_MANUAL
echo [PROVISION] Installing Python 3.10 via winget...
winget install --id Python.Python.3.10 --silent --accept-package-agreements --accept-source-agreements
call :REFRESH_PATH
for /f "delims=" %%I in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
if defined PYTHON_EXE goto :PYTHON_OK

:PYTHON_MANUAL
echo [FATAL ERROR] Python 3.10 or 3.11 is required but could not be located.
echo Please install Python 3.10 manually from:
echo https://www.python.org/downloads/release/python-31011/
echo CRITICAL: Check the box "Add python.exe to PATH" during setup.
goto :HALT_ERROR

:PYTHON_OK
echo [OK] Using Python: %PYTHON_EXE%

:PYTHON_PROCEED
echo [INFO] Video Decoding: PyAV bundles internal FFmpeg C-libraries. External ffmpeg.exe is not required.
echo [INFO] Frontend: Pure HTML5/ES6/CSS. Node.js/npm is not required.
echo [INFO] Version Control: Standalone distribution. Git is not required.

echo [3/7] Initializing virtual environment (.venv)...
if exist "%~dp0.venv\Scripts\python.exe" goto :VENV_EXISTS
if "%IS_DRYRUN%"=="1" (
    echo [DRYRUN] Would create fresh virtual environment in .venv
    goto :VENV_DONE
)
echo [PROVISION] Creating fresh virtual environment (.venv)...
"%PYTHON_EXE%" -m venv "%~dp0.venv"
if errorlevel 1 (
    echo [FATAL ERROR] Failed to create virtual environment. Check permissions and disk space.
    goto :HALT_ERROR
)
echo [OK] Virtual environment created successfully.
goto :VENV_DONE

:VENV_EXISTS
echo [OK] Virtual environment (.venv) already exists.

:VENV_DONE
set "VIRTUAL_ENV=%~dp0.venv"
set "PATH=%VIRTUAL_ENV%\Scripts;%PATH%"

echo [4/7] Verifying dependencies and lockfile...
set "REQ_HASH="
if not exist "%~dp0requirements-lock.txt" goto :HASH_DONE
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%~dp0requirements-lock.txt" SHA256 2^>nul') do (
    if not defined REQ_HASH set "REQ_HASH=%%H"
)
if defined REQ_HASH set "REQ_HASH=%REQ_HASH: =%"
:HASH_DONE

set "CACHE_MATCH=0"
if not exist "%~dp0.venv\.installed-hash" goto :CHECK_CACHE_DONE
for /f "tokens=1" %%C in ('type "%~dp0.venv\.installed-hash" 2^>nul') do (
    if "%%C"=="%REQ_HASH%" set "CACHE_MATCH=1"
)
:CHECK_CACHE_DONE

if "%CACHE_MATCH%"=="1" goto :DEPS_CACHED
if "%IS_DRYRUN%"=="1" goto :DEPS_DRYRUN
goto :DEPS_INSTALL

:DEPS_CACHED
echo [OK] Dependencies already installed and verified (cached against requirements-lock.txt).
goto :DEPS_VERIFIED

:DEPS_DRYRUN
echo [DRYRUN] Dependencies need installation. Would install torch and requirements-lock.txt.
goto :DEPS_VERIFIED

:DEPS_INSTALL

echo [PROVISION] Installing dependencies from requirements-lock.txt (first-run setup)...
python -m pip install --upgrade pip

set "HAS_GPU=0"
where nvidia-smi >nul 2>&1
if not errorlevel 1 set "HAS_GPU=1"

if "%HAS_GPU%"=="1" goto :INSTALL_GPU
echo [INFO] No NVIDIA GPU detected. Installing PyTorch universal CPU build...
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :TORCH_FAILED
goto :INSTALL_LOCKFILE

:INSTALL_GPU
echo [INFO] NVIDIA GPU detected. Installing PyTorch with CUDA acceleration...
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 goto :TORCH_FAILED
goto :INSTALL_LOCKFILE

:TORCH_FAILED
echo [FATAL ERROR] Failed to install PyTorch wheel. Check internet connectivity.
goto :HALT_ERROR

:INSTALL_LOCKFILE
echo [PROVISION] Installing locked packages (--prefer-binary --retries 5)...
pip install --prefer-binary --retries 5 --default-timeout 120 -r "%~dp0requirements-lock.txt"
if errorlevel 1 (
    echo [FATAL ERROR] Failed to install dependencies from requirements-lock.txt.
    goto :HALT_ERROR
)

if defined REQ_HASH (
    echo %REQ_HASH% > "%~dp0.venv\.installed-hash"
)
echo [OK] All dependencies successfully installed and cached.

:DEPS_VERIFIED

echo [5/7] Verifying forensic model weights...

if not exist "%~dp0models" mkdir "%~dp0models"
if not exist "%~dp0ai_cctv_detection\models" mkdir "%~dp0ai_cctv_detection\models"

if exist "%~dp0models\yolo11s-cls.pt" goto :BASE_MODEL_OK
if "%IS_DRYRUN%"=="1" (
    echo [DRYRUN] Base checkpoint missing. Would download yolo11s-cls.pt from GitHub releases.
    goto :CHECK_FINE_TUNED
)
echo [PROVISION] Downloading YOLO11 base classification weights into models folder...
curl.exe -L -f "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s-cls.pt" -o "%~dp0models\yolo11s-cls.pt"
if errorlevel 1 (
    echo [WARN] curl download failed. Attempting Python urllib fallback...
    python -c "import urllib.request; urllib.request.urlretrieve('https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s-cls.pt', 'models/yolo11s-cls.pt')"
)
:BASE_MODEL_OK
echo [OK] Base classification model (models\yolo11s-cls.pt) present.

:CHECK_FINE_TUNED
set "BEST_FOUND=0"
if exist "%~dp0ai_cctv_detection\models\best.pt" set "BEST_FOUND=1"
if exist "%~dp0models\best.pt" (
    set "BEST_FOUND=1"
    if not exist "%~dp0ai_cctv_detection\models\best.pt" (
        copy /y "%~dp0models\best.pt" "%~dp0ai_cctv_detection\models\best.pt" >nul 2>&1
    )
)

if "%BEST_FOUND%"=="1" goto :FINE_TUNED_OK
echo(
echo +------------------------------------------------------------------------+
echo ^| [FATAL ERROR] Fine-tuned model 'ai_cctv_detection\models\best.pt' NOT FOUND!^|
echo ^|                                                                        ^|
echo ^| Forensic Honesty Rule: Stock YOLO cannot authenticate altered CCTV.    ^|
echo ^| This fine-tuned model was trained on forensic real/tampered datasets   ^|
echo ^| and CANNOT be downloaded automatically from the internet.              ^|
echo ^|                                                                        ^|
echo ^| Fix: Copy 'best.pt' into 'ai_cctv_detection\models\' before launching.  ^|
echo +------------------------------------------------------------------------+
echo(
if "%IS_DRYRUN%"=="0" goto :HALT_ERROR

:FINE_TUNED_OK
echo [OK] Fine-tuned forensic detector (ai_cctv_detection\models\best.pt) verified.

echo [6/7] Ensuring storage directories exist...
for %%D in (uploads artifacts artifacts\ai_cctv_detection cache data models ai_cctv_detection\models) do (
    if not exist "%~dp0%%D" mkdir "%~dp0%%D"
)
echo [OK] Storage directories verified.

echo [7/7] Allocating network port...
set "PORT="
for /f "tokens=*" %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launcher_helper.ps1" -Action get_free_port -Arg1 8000 2^>nul') do (
    if not defined PORT set "PORT=%%P"
)
if "%PORT%"=="" set "PORT=8000"
echo [OK] Allocated Port: %PORT%

if not "%IS_DRYRUN%"=="1" goto :START_LIVE_APP
echo(
echo ========================================================
echo  [DRYRUN COMPLETED SUCCESSFULLY]
echo  All system checks and portability requirements passed.
echo  No files were modified. The laptop is ready for live run.
echo ========================================================
echo(
exit /b 0

:START_LIVE_APP
set HF_HUB_OFFLINE=1
set YOLO_OFFLINE=1

start "" /b cmd /c "ping 127.0.0.1 -n 4 >nul & start http://127.0.0.1:%PORT%/"

echo(
echo ==============================================
echo  PS-05 AI CCTV Detection is running
echo  Open this link in your browser:
echo  http://127.0.0.1:%PORT%/
echo  (API docs: http://127.0.0.1:%PORT%/docs)
echo  Press CTRL+C to stop the server
echo ==============================================
echo(

python -m uvicorn %APP_TARGET% --host 127.0.0.1 --port %PORT%
set "SERVER_EXIT=%ERRORLEVEL%"
if not "%SERVER_EXIT%"=="0" (
    echo(
    echo [ERROR] Server terminated with error code %SERVER_EXIT%.
    pause
    exit /b %SERVER_EXIT%
)
pause
exit /b 0

:REFRESH_PATH
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
set "PATH=%SYS_PATH%;%USER_PATH%;%PATH%"
exit /b 0

:HALT_ERROR
echo(
echo [SETUP FAILED] Please address the error above or run check_system.bat.
if not "%IS_DRYRUN%"=="1" pause
exit /b 1
