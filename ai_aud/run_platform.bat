@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: PS-05 Audio Forensics Universal Platform Launcher
:: Automated provisioning for clean Windows 10/11 machines
:: ============================================================

cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "APP_TARGET=main_standalone:app"

:: Parse CLI arguments
set "DRYRUN=0"
set "RESET=0"
if /i "%~1"=="/dryrun" set "DRYRUN=1"
if /i "%~1"=="--dryrun" set "DRYRUN=1"
if /i "%~1"=="/reset" set "RESET=1"
if /i "%~1"=="--reset" set "RESET=1"

:: Setup logging
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"
set "TIMESTAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "LOG_FILE=%PROJECT_ROOT%\logs\setup_%TIMESTAMP%.txt"

call :log "============================================================"
call :log "  PS-05 Audio Forensics Platform Launcher"
call :log "  Automated Setup and Standalone Server Execution"
call :log "============================================================"
if %DRYRUN% equ 1 call :log "  MODE: DRY-RUN [inspections only, no modifications]"
if %RESET% equ 1 call :log "  MODE: RESET [virtual environment will be recreated]"
call :log_blank

:: Reset handling
if %RESET% equ 1 (
    call :log "Reset requested: removing .venv and installation markers..."
    if exist "%PROJECT_ROOT%\.venv" (
        powershell -NoProfile -Command "Remove-Item -Recurse -Force '%PROJECT_ROOT%\.venv'" >nul 2>&1
    )
    if exist "%PROJECT_ROOT%\.deps_installed" del /f /q "%PROJECT_ROOT%\.deps_installed" >nul 2>&1
    call :log "Reset completed."
    call :log_blank
)

:: [1/7] System Architecture and Storage Check
call :log "[1/7] Verifying System Architecture and Storage..."
set "IS_64BIT=0"
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" set "IS_64BIT=1"
if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "IS_64BIT=1"

if %IS_64BIT% neq 1 (
    call :log "[ERROR] 64-bit Windows is strictly required by PyTorch and Fairseq."
    pause
    exit /b 1
)

powershell -NoProfile -Command "$freeGB = [math]::Round((Get-Item '%PROJECT_ROOT%').PSDrive.Free / 1GB, 1); Write-Host ('      Storage: ' + $freeGB + ' GB free on drive.'); if ($freeGB -lt 10.0) { Write-Host '      [WARNING] Free disk space is below 10 GB. Model weights require ~5 GB.' } else { Write-Host '      Storage space is sufficient.' }"

:: [2/7] Prerequisites: Python 3.10 and VC++ Runtime
call :log "[2/7] Checking Runtime Prerequisites [Python 3.10 and VC++ Runtime]..."
call :detect_python

if "%PY_CMD%"=="" (
    call :log "      Python 3.10 was not detected on this system."
    if %DRYRUN% equ 1 (
        call :log "      [DRY-RUN] Would install Python 3.10 via winget: winget install Python.Python.3.10"
    ) else (
        call :log "      Attempting automated installation of Python 3.10 via winget..."
        winget --version >nul 2>&1
        if !errorlevel! equ 0 (
            winget install --id Python.Python.3.10 --silent --accept-package-agreements --accept-source-agreements
            call :detect_python
        ) else (
            call :log "      [ERROR] winget is not available on this machine."
            call :log "      Please install Python 3.10 manually from:"
            call :log "      https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
            call :log "      IMPORTANT: Tick 'Add Python to PATH' during installation."
            pause
            exit /b 1
        )
    )
)

if not "%PY_CMD%"=="" (
    for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do set "PY_VER=%%v"
    call :log "      Using Python runtime: !PY_VER! [%PY_CMD%]"
)

:: Check VC++ Runtime
powershell -NoProfile -Command "$vc = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64' -ErrorAction SilentlyContinue; if ($vc -and $vc.Installed -eq 1) { Write-Host '      Microsoft Visual C++ Redistributable is installed.' } else { exit 1 }"
if !errorlevel! neq 0 (
    call :log "      Microsoft Visual C++ 2015-2022 Redistributable not detected."
    if %DRYRUN% equ 1 (
        call :log "      [DRY-RUN] Would install VC++ via winget: winget install Microsoft.VCRedist.2015+.x64"
    ) else (
        winget --version >nul 2>&1
        if !errorlevel! equ 0 (
            call :log "      Installing Microsoft Visual C++ Redistributable via winget..."
            winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements
        ) else (
            call :log "      [NOTICE] If PyTorch fails to load, install VC++ Redistributable from:"
            call :log "      https://aka.ms/vs/17/release/vc_redist.x64.exe"
        )
    )
)

:: [3/7] Virtual Environment & Dependencies
call :log "[3/7] Setting Up Isolated Virtual Environment [.venv]..."
if %DRYRUN% equ 1 (
    call :log "      [DRY-RUN] Would verify/create .venv, upgrade pip to 24.0, and install requirements-lock.txt"
) else (
    call :setup_virtualenv
    if !errorlevel! neq 0 (
        call :log "      [ERROR] Virtual environment or dependency setup failed."
        pause
        exit /b 1
    )
)

:: [4/7] Model Checkpoints Verification and Downloading
call :log "[4/7] Checking W2V2-AASIST Model Checkpoints..."
set "MODELS_DIR=%PROJECT_ROOT%\audio_forensics\models"
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

set "XLSR_FILE=%MODELS_DIR%\xlsr2_300m.pt"
set "AASIST_FILE=%MODELS_DIR%\LA_model.pth"

call :check_or_download_model "%XLSR_FILE%" "https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt" "Base XLS-R 300M Model" "2147483648"
call :check_or_download_model "%AASIST_FILE%" "https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST/resolve/main/LA_model.pth" "AASIST Model Weights" "1073741824"

:: [5/7] Audio Decoders Check
call :log "[5/7] Checking Audio Decoders..."
call :log "      SoundFile + bundled PyAV FFmpeg libraries active [external ffmpeg.exe not needed]."

:: [6/7] Working Directories & Storage Setup
call :log "[6/7] Ensuring Standard Storage Directories Exist..."
if not exist "%PROJECT_ROOT%\uploads" mkdir "%PROJECT_ROOT%\uploads"
if not exist "%PROJECT_ROOT%\artifacts\audio_forensics" mkdir "%PROJECT_ROOT%\artifacts\audio_forensics"
if not exist "%PROJECT_ROOT%\cache" mkdir "%PROJECT_ROOT%\cache"
if not exist "%PROJECT_ROOT%\data_audio\bonafide" mkdir "%PROJECT_ROOT%\data_audio\bonafide"
if not exist "%PROJECT_ROOT%\data_audio\spoof" mkdir "%PROJECT_ROOT%\data_audio\spoof"
call :log "      Storage directories ready."

:: [7/7] Server Port Allocation & Execution
call :log "[7/7] Allocating Server Port..."
set "PORT=8000"
powershell -NoProfile -Command "$p=8000; while(Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue){$p++}; Set-Content -Path '%TEMP%\ps05_port.txt' -Value $p" >nul 2>&1
if exist "%TEMP%\ps05_port.txt" (
    set /p PORT=<"%TEMP%\ps05_port.txt"
    del "%TEMP%\ps05_port.txt" >nul 2>&1
)

:: Offline Runtime Environment Flags
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"

call :log_blank
call :log "=============================================="
call :log " PS-05 Audio Forensics is running"
call :log " Open this link in your browser:"
call :log " http://127.0.0.1:%PORT%/"
call :log " [API docs: http://127.0.0.1:%PORT%/docs]"
call :log " Press CTRL+C to stop the server"
call :log "=============================================="
call :log_blank

if %DRYRUN% equ 1 goto :dryrun_exit

:: Auto-launch browser after 3 seconds in background
start /min powershell -NoProfile -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:%PORT%/'"

:: Run Uvicorn in foreground
"%PROJECT_ROOT%\.venv\Scripts\python.exe" -m uvicorn %APP_TARGET% --host 127.0.0.1 --port %PORT%

if !errorlevel! equ 0 (
    call :log "Server stopped normally."
) else if !errorlevel! equ -1 (
    call :log "Server stopped by user."
) else if !errorlevel! equ -1073741510 (
    call :log "Server stopped by user."
) else (
    call :log "[ERROR] Server exited unexpectedly with code !errorlevel!."
    pause
)
goto :end

:dryrun_exit
call :log "[DRY-RUN] Finished simulation. Server execution skipped."
exit /b 0

:end
exit /b 0


:: =============================================================
:: Subroutines
:: =============================================================

:detect_python
set "PY_CMD="
py -3.10 --version >nul 2>&1
if !errorlevel! equ 0 set "PY_CMD=py -3.10" & exit /b 0

python --version 2>&1 | findstr /i "3.10" >nul 2>&1
if !errorlevel! equ 0 set "PY_CMD=python" & exit /b 0

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY_CMD=\"%LOCALAPPDATA%\Programs\Python\Python310\python.exe\"" & exit /b 0
if exist "%ProgramFiles%\Python310\python.exe" set "PY_CMD=\"%ProgramFiles%\Python310\python.exe\"" & exit /b 0
if exist "C:\Python310\python.exe" set "PY_CMD=\"C:\Python310\python.exe\"" & exit /b 0
exit /b 0


:setup_virtualenv
if not exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    call :log "      Creating virtual environment in %PROJECT_ROOT%\.venv..."
    %PY_CMD% -m venv "%PROJECT_ROOT%\.venv"
    if !errorlevel! neq 0 (
        call :log "      [ERROR] Failed to create virtual environment."
        exit /b 1
    )
)

set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

:: Ensure pip is strictly below 24.1 (pinned to 24.0)
"%VENV_PYTHON%" -m pip install "pip==24.0" --quiet --disable-pip-version-check >nul 2>&1

if not exist "%PROJECT_ROOT%\.deps_installed" (
    call :log "      First-time dependency installation detected."
    
    :: Detect Hardware GPU
    nvidia-smi >nul 2>&1
    if !errorlevel! equ 0 (
        call :log "      NVIDIA GPU detected. Installing PyTorch with CUDA acceleration..."
        "%VENV_PYTHON%" -m pip install torch torchaudio --default-timeout 100 --extra-index-url https://download.pytorch.org/whl/cu121
        if !errorlevel! neq 0 (
            call :log "      CUDA PyTorch installation failed. Falling back to CPU build..."
            "%VENV_PYTHON%" -m pip install torch torchaudio --default-timeout 100 --extra-index-url https://download.pytorch.org/whl/cpu
        )
    ) else (
        call :log "      No NVIDIA GPU found. Installing PyTorch CPU build..."
        "%VENV_PYTHON%" -m pip install torch torchaudio --default-timeout 100 --extra-index-url https://download.pytorch.org/whl/cpu
    )

    if !errorlevel! neq 0 (
        call :log "      [ERROR] PyTorch installation failed. Check internet connectivity."
        exit /b 1
    )

    call :log "      Installing core dependencies from requirements-lock.txt..."
    call :log "      Using pre-bundled offline wheels from wheels/ folder..."
    
    if exist "%PROJECT_ROOT%\wheels" (
        "%VENV_PYTHON%" -m pip install --no-index --find-links "%PROJECT_ROOT%\wheels" numpy fairseq --quiet >nul 2>&1
    )

    "%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%\requirements-lock.txt" --find-links "%PROJECT_ROOT%\wheels" --prefer-binary --default-timeout 100
    if !errorlevel! neq 0 (
        call :log "      [WARNING] Retrying dependency install with fallback index..."
        "%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%\requirements-lock.txt" --find-links "%PROJECT_ROOT%\wheels" --prefer-binary --default-timeout 100 --index-url https://mirrors.aliyun.com/pypi/simple/
    )

    if !errorlevel! neq 0 (
        call :log "      [ERROR] Failed to install all dependencies from requirements-lock.txt."
        exit /b 1
    )

    call :log "      Dependencies verified. Writing installation marker..."
    echo installed > "%PROJECT_ROOT%\.deps_installed"
) else (
    call :log "      Dependencies verified [.deps_installed present]."
)
exit /b 0


:check_or_download_model
set "M_FILE=%~1"
set "M_URL=%~2"
set "M_NAME=%~3"
set "M_THRESH=%~4"

if not exist "%M_FILE%" goto :model_not_found

powershell -NoProfile -Command "$item = Get-Item '%M_FILE%' -ErrorAction SilentlyContinue; if ($item -and $item.Length -ge %M_THRESH%) { exit 0 } else { exit 1 }"
if !errorlevel! equ 0 (
    call :log "      Found %M_NAME% [size verified]."
    goto :eof
)

call :log "      [WARNING] %M_NAME% is incomplete or corrupted. Re-downloading..."
del /f /q "%M_FILE%" >nul 2>&1

:model_not_found
if %DRYRUN% equ 1 (
    call :log "      [DRY-RUN] Would download %M_NAME% from %M_URL%"
    goto :eof
)

call :log "      Downloading %M_NAME%..."
call :log "      Source: %M_URL%"

curl.exe -V >nul 2>&1
if !errorlevel! equ 0 (
    curl.exe -4 -L -C - --retry 3 --retry-delay 2 -o "%M_FILE%" "%M_URL%"
) else (
    powershell -NoProfile -Command "Start-BitsTransfer -Source '%M_URL%' -Destination '%M_FILE%'"
)

if not exist "%M_FILE%" (
    call :log "      [WARNING] Failed to download %M_NAME%."
    call :log "      Please manually download the file from:"
    call :log "      %M_URL%"
    call :log "      and save it into: %MODELS_DIR%\"
) else (
    call :log "      Successfully obtained %M_NAME%."
)
goto :eof


:log
echo %~1
if defined LOG_FILE echo [%DATE% %TIME%] %~1>>"%LOG_FILE%" 2>nul
goto :eof

:log_blank
echo(
if defined LOG_FILE echo(>>"%LOG_FILE%" 2>nul
goto :eof
