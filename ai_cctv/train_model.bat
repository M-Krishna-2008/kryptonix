@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================================
echo  PS-05: AI CCTV Model Training & Calibration Launcher
echo ========================================================

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run run_platform.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

set "REAL_DIR=data_raw\real"
set "FAKE_DIR=data_raw\fake"

echo Enter folder containing authentic CCTV videos [default: data_raw\real]:
set /p USER_REAL=""
if not "%USER_REAL%"=="" set "REAL_DIR=%USER_REAL%"

echo Enter folder containing AI-generated CCTV videos [default: data_raw\fake]:
set /p USER_FAKE=""
if not "%USER_FAKE%"=="" set "FAKE_DIR=%USER_FAKE%"

if not exist "%REAL_DIR%" (
    echo [ERROR] Real videos folder '%REAL_DIR%' does not exist.
    pause
    exit /b 1
)

if not exist "%FAKE_DIR%" (
    echo [ERROR] Fake videos folder '%FAKE_DIR%' does not exist.
    pause
    exit /b 1
)

echo.
echo [1/4] Building dataset with split-by-source-video...
python tools\build_dataset.py "%REAL_DIR%" "%FAKE_DIR%" --output-dir data
if %errorlevel% neq 0 (
    echo [ERROR] Dataset building failed.
    pause
    exit /b 1
)

echo.
echo [2/4] Testing for metadata shortcut learning...
python tools\metadata_check.py --manifest data\manifest.json

echo.
echo [3/4] Fine-tuning YOLO11-cls (imgsz=448, mild augmentation)...
python tools\train.py --data-dir data --output-weights ai_cctv_detection\models\best.pt
if %errorlevel% neq 0 (
    echo [ERROR] Training failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Fitting Platt scaling calibration on validation split...
python tools\calibrate.py --model ai_cctv_detection\models\best.pt --val-dir data\val
if %errorlevel% neq 0 (
    echo [ERROR] Calibration failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Training and Calibration Complete!
echo  Weights saved to: ai_cctv_detection\models\best.pt
echo  Now restart run_platform.bat to run inference.
echo ========================================================
pause
