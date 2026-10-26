@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================================
echo  PS-05 Transfer Package Integrity Verification
echo  Directory: %~dp0
echo ========================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\verify_helper.ps1" -TargetDir "%~dp0."
set "VERIFY_EXIT=%ERRORLEVEL%"

echo(
if "%VERIFY_EXIT%"=="0" (
    echo [SUCCESS] All files verified successfully.
) else (
    echo [ERROR] Package verification failed.
)
if not "%~1"=="--no-pause" pause
exit /b %VERIFY_EXIT%
