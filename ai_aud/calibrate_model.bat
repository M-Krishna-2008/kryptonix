@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   PS-05 Audio Forensics - Decision Threshold Calibration
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run run_platform.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

set /p BONAFIDE_DIR="Enter path to bona-fide (authentic) audio directory [default: data_audio\bonafide]: "
if "%BONAFIDE_DIR%"=="" set BONAFIDE_DIR=data_audio\bonafide

set /p SPOOF_DIR="Enter path to spoofed (synthetic) audio directory [default: data_audio\spoof]: "
if "%SPOOF_DIR%"=="" set SPOOF_DIR=data_audio\spoof

echo.
echo Running calibration on:
echo   Bona-fide: %BONAFIDE_DIR%
echo   Spoof:     %SPOOF_DIR%
echo.

python tools\calibrate.py "%BONAFIDE_DIR%" "%SPOOF_DIR%" --save

echo.
pause
