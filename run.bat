@echo off
setlocal
cd /d "%~dp0"
set "ARGS=%*"
set "ARGS=%ARGS:/dryrun=-DryRun%"
set "ARGS=%ARGS:/setup=-Setup%"
set "ARGS=%ARGS:/reset=-Reset%"
set "ARGS=%ARGS:/nobrowser=-NoBrowser%"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\launch.ps1" %ARGS%
