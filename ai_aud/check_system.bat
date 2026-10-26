@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   PS-05 Audio Forensics - System Diagnostic Check
echo ============================================================
echo.

:: 1. Windows Version and Architecture
echo [1/6] Operating System and Hardware Architecture:
powershell -NoProfile -Command "$os = Get-CimInstance Win32_OperatingSystem; $arch = if ([Environment]::Is64BitOperatingSystem) { '64-bit (x64)' } else { '32-bit (x86)' }; Write-Host ('  OS Name:         ' + $os.Caption); Write-Host ('  OS Version:      ' + $os.Version); Write-Host ('  Architecture:    ' + $arch)"

:: 2. Disk Space
echo.
echo [2/6] Storage Space Check:
powershell -NoProfile -Command "$drive = (Get-Item '%~dp0').PSDrive; $freeGB = [math]::Round($drive.Free / 1GB, 2); Write-Host ('  Current Drive:   ' + $drive.Name + ' [' + $freeGB + ' GB free]'); if ($freeGB -lt 10) { Write-Host '  [WARNING] Low disk space! Less than 10 GB free.' -ForegroundColor Yellow } else { Write-Host '  Storage Status:  Sufficient [greater than 10 GB free]' }"

:: 3. Software & Tooling Availability
echo.
echo [3/6] System Tools Availability:

call :check_python
call :check_winget
call :check_git
call :check_ffmpeg
call :check_node
call :check_gpu
call :check_vcredist

:: 4. Network Reachability
echo.
echo [4/6] Network Reachability:
powershell -NoProfile -Command "$hosts = @(@{Name='PyPI package repo'; Url='https://pypi.org'}, @{Name='Hugging Face models'; Url='https://huggingface.co'}, @{Name='Meta Fairseq CDN'; Url='https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt'}); foreach ($h in $hosts) { try { $req = [System.Net.WebRequest]::Create($h.Url); $req.Method = 'HEAD'; $req.Timeout = 4000; $res = $req.GetResponse(); Write-Host ('  ' + $h.Name.PadRight(30) + ': REACHABLE'); $res.Close() } catch { Write-Host ('  ' + $h.Name.PadRight(30) + ': UNREACHABLE') } }"

:: 5. Model Files Verification
echo.
echo [5/6] Model Weights Status:
powershell -NoProfile -Command "$models = @(@{Name='xlsr2_300m.pt'; Path='audio_forensics\models\xlsr2_300m.pt'}, @{Name='LA_model.pth'; Path='audio_forensics\models\LA_model.pth'}); foreach ($m in $models) { if (Test-Path $m.Path) { $item = Get-Item $m.Path; Write-Host ('  ' + $m.Name.PadRight(20) + ': PRESENT [' + [math]::Round($item.Length / 1MB, 1) + ' MB]') } else { Write-Host ('  ' + $m.Name.PadRight(20) + ': MISSING [will download on first run]') } }"

:: 6. Bundled Offline Wheels Check
echo.
echo [6/6] Bundled Offline Wheels Status:
powershell -NoProfile -Command "$whls = Get-ChildItem -Path 'wheels' -Filter '*.whl' -ErrorAction SilentlyContinue; if ($whls) { foreach ($w in $whls) { Write-Host ('  Bundled wheel:   ' + $w.Name + ' [' + [math]::Round($w.Length/1MB, 1) + ' MB]') } } else { Write-Host '  No pre-bundled wheels found in wheels/ folder.' }"

echo.
echo ============================================================
echo   Diagnostic Check Complete
echo ============================================================
echo.
pause
exit /b 0

:check_python
py -3.10 --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('py -3.10 --version 2^>^&1') do echo   Python 3.10:     FOUND [%%v via py launcher]
    exit /b 0
)
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python --version 2>&1 | findstr /i "3.10" >nul
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Python 3.10:     FOUND [%%v in PATH]
        exit /b 0
    )
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Python:          FOUND [%%v - Fairseq requires Python 3.10]
    exit /b 0
)
echo   Python 3.10:     NOT FOUND [will be provisioned automatically]
exit /b 0

:check_winget
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('winget --version') do echo   Winget:          FOUND [v%%v]
) else (
    echo   Winget:          NOT FOUND [pre-installed on Windows 10 1809+ / Windows 11]
)
exit /b 0

:check_git
git --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('git --version') do echo   Git:             FOUND [%%v - optional]
) else (
    echo   Git:             NOT FOUND [not required; project uses offline wheels]
)
exit /b 0

:check_ffmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    echo   FFmpeg CLI:      FOUND [optional]
) else (
    echo   FFmpeg CLI:      NOT FOUND [not required; PyAV bundles static FFmpeg]
)
exit /b 0

:check_node
node --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('node --version') do echo   Node.js:         FOUND [%%v - optional]
) else (
    echo   Node.js:         NOT FOUND [not required; frontend is vanilla HTML/JS]
)
exit /b 0

:check_gpu
nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%g in ('powershell -NoProfile -Command "(nvidia-smi --query-gpu=name --format=csv,noheader) -join ', '"') do echo   NVIDIA GPU:      FOUND [%%g]
) else (
    echo   NVIDIA GPU:      NOT FOUND [CPU execution mode will be used]
)
exit /b 0

:check_vcredist
powershell -NoProfile -Command "$vc = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64' -ErrorAction SilentlyContinue; if ($vc.Installed -eq 1) { Write-Host ('  VC++ Runtime:    FOUND [Installed v' + $vc.Version + ']') } else { Write-Host '  VC++ Runtime:    NOT FOUND [will be provisioned by launcher]' }"
exit /b 0
