@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\package_builder.ps1" -SourceRoot "%~dp0."
exit /b %ERRORLEVEL%
