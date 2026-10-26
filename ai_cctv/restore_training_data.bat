@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~1"=="" (
    echo [ERROR] Archive source folder is required.
    echo Usage: restore_training_data.bat ^<archive_folder^>
    echo Example: restore_training_data.bat "D:\Forensics_Archive\PS05_Training_Data"
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\archive_manager.ps1" -Action restore -SourceRoot "%~dp0." -DestFolder "%~1"
exit /b %ERRORLEVEL%
