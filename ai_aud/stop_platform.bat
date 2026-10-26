@echo off
setlocal
cd /d "%~dp0"

echo Stopping PS-05 Audio Forensics server...

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*main_standalone*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Stopped PID:' $_.ProcessId }"

echo Platform stopped.
