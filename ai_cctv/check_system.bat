@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_system.ps1" -TargetDir "%~dp0."
set "DIAG_EXIT=%ERRORLEVEL%"

echo(
if "%DIAG_EXIT%"=="0" goto :DIAG_OK
if "%DIAG_EXIT%"=="1" goto :DIAG_SETUP
goto :DIAG_INCOMPATIBLE

:DIAG_OK
echo [STATUS] Diagnostic completed: System is READY (Exit Code 0).
goto :DIAG_END

:DIAG_SETUP
echo [STATUS] Diagnostic completed: First-run setup is REQUIRED (Exit Code 1).
echo Run run_platform.bat to initialize the platform.
goto :DIAG_END

:DIAG_INCOMPATIBLE
echo [STATUS] Diagnostic completed: System is INCOMPATIBLE (Exit Code 2).
echo Please review the diagnostic log above.
goto :DIAG_END

:DIAG_END
echo(
if not "%1"=="--no-pause" (
    pause
)
exit /b %DIAG_EXIT%
