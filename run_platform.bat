@echo off
setlocal
title PS-05 Forensics Platform
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\launch.ps1" %*
if errorlevel 1 (
    echo.
    echo Platform launcher terminated with error code %errorlevel%.
    pause
)
