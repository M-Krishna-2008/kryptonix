@echo off
setlocal
cd /d "%~dp0"

echo Stopping PS-05 AI CCTV Detection server...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr "LISTENING" ^| findstr ":8000 :8001 :8002 :8003 :8004 :8005"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo Terminated process on port (PID %%a)
)

echo Server stopped.
