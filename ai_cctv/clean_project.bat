@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "DO_CLEAN=0"
set "DAYS_OLD=30"

if /i "%~1"=="/yes" set "DO_CLEAN=1"
if /i "%~1"=="-yes" set "DO_CLEAN=1"
if /i "%~1"=="--yes" set "DO_CLEAN=1"

if not "%~2"=="" (
    set "DAYS_OLD=%~2"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\clean_helper.ps1" -TargetDir "%~dp0." -ApplyClean %DO_CLEAN% -Days %DAYS_OLD%
exit /b %ERRORLEVEL%
