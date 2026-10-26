@echo off
setlocal
cd /d "%~dp0"

echo =========================================================================
echo  Stopping PS-05 Digital Evidence Platform Server...
echo =========================================================================

powershell -Command "Get-NetTCPConnection -LocalPort 8000,8001,8002,8003,8004,8005 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped PID: ' + $_.OwningProcess) }"

echo.
echo [SUCCESS] Platform server stopped.
ping 127.0.0.1 -n 2 >nul
