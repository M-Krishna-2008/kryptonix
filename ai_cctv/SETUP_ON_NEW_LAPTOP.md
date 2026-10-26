# Setup Guide: Running PS-05 on a Fresh Windows Laptop

This guide explains how to deploy and run the **AI CCTV Tampering and Deepfake Detection** module on any Windows 10 or Windows 11 laptop with no development tools pre-installed.

---

## Quick Start (3-Step Guide)

### Step 1: Copy the Project Folder
Copy the entire `yolo project` folder to the target laptop (e.g., to your `Desktop`, `Documents`, or `Downloads` folder).  
*Make sure the folder contains `ai_cctv_detection/models/best.pt`.*

### Step 2: (Optional Pre-Flight Check) Double-Click `check_system.bat`
Double-click `check_system.bat` in the folder. It will scan your laptop's hardware, available disk space, Visual C++ runtimes, and model files, and output a status verdict:
- **`Exit Code 0 (READY)`**: Machine is fully prepared.
- **`Exit Code 1 (FIRST-RUN SETUP NEEDED)`**: Machine is compatible; launcher will provision dependencies automatically.
- **`Exit Code 2 (INCOMPATIBLE)`**: Incompatible system (e.g. 32-bit Windows or less than 5 GB disk space).

### Step 3: Double-Click `run_platform.bat`
Double-click `run_platform.bat`.
- The launcher automatically detects your hardware, sets up an isolated virtual environment (`.venv`), installs the locked dependencies, allocates a free port, and **opens your default web browser automatically** to `http://127.0.0.1:8000/`.
- Press `CTRL+C` in the command window whenever you wish to shut down the server.

---

## First Run vs. Subsequent Runs

| Run Phase | Duration | Network Required? | Actions Performed |
|---|---|---|---|
| **First Run** | ~3 to 7 minutes | **Yes** (to fetch Python/wheels) | - Checks 64-bit Windows & disk space.<br>- Installs Python 3.10 and VC++ Redistributable via `winget` (if missing).<br>- Creates `.venv` virtual environment.<br>- Installs PyTorch (CUDA GPU build if NVIDIA present, CPU build if Intel/AMD) and dependencies from `requirements-lock.txt`.<br>- Downloads base model if missing.<br>- Saves verification hash to `.venv/.installed-hash`. |
| **Subsequent Runs** | **< 3 seconds** | **No** (100% Offline) | - Verifies existing `.venv` and cached hash.<br>- Skips all installation steps instantly.<br>- Launches Uvicorn server and opens browser. |

---

## Offline Deployment Variant (For Air-Gapped / Forensic Laptops)

If the destination laptop is in a secure, air-gapped forensic lab with **NO internet access**:

1. **Prepare on an Online Machine**:
   - Run `run_platform.bat` on an internet-connected Windows laptop once.
   - Let it complete the full setup so that `.venv`, `models/yolo11s-cls.pt`, and `ai_cctv_detection/models/best.pt` are all fully populated.
2. **Transfer via USB Drive**:
   - Copy the entire project directory (including the `.venv` folder) onto an external USB hard drive or flash drive.
3. **Run Offline on Destination Machine**:
   - Plug the USB into the air-gapped laptop and copy the folder to the local drive.
   - Double-click `run_platform.bat`. Because `.venv` and `.installed-hash` already exist, the launcher starts immediately in offline mode (`YOLO_OFFLINE=1`, `HF_HUB_OFFLINE=1`) without attempting any network calls.

---

## Advanced Command-Line Flags

Open Command Prompt in the project folder to run specialized commands:

- **Dry-run validation** (Checks everything without modifying files or installing):
  ```cmd
  run_platform.bat /dryrun
  ```
- **Clean Reset** (Deletes `.venv` and cached state, forcing a fresh setup from scratch):
  ```cmd
  run_platform.bat /reset
  ```

---

## Top 5 Troubleshooting Scenarios

### 1. `Python 3.10 is required but could not be located`
- **Cause**: Python is not installed and `winget` is unavailable or blocked by corporate policy.
- **Fix**: Download Python 3.10.11 directly from [Python.org](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe). Run the installer and **check the box: `[X] Add python.exe to PATH`**.

### 2. `Fine-tuned model 'ai_cctv_detection\models\best.pt' NOT FOUND`
- **Cause**: The fine-tuned weights file was excluded during folder copy or git clone.
- **Fix**: Copy `best.pt` (approx. 11 MB) from your backup or teammate's drive into `ai_cctv_detection\models\best.pt`. The platform strictly forbids fake/stock weights for forensic integrity.

### 3. `Microsoft Visual C++ 2015-2022 x64 Redistributable is missing`
- **Cause**: Brand-new Windows installations lack standard C++ runtime DLLs required by PyTorch and OpenCV.
- **Fix**: Download and run the official installer from Microsoft: [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe). Once installed, double-click `run_platform.bat`.

### 4. Port 8000 Already in Use
- **Cause**: Another service (Docker, IIS, another dev server) is occupying port 8000.
- **Fix**: `run_platform.bat` automatically detects port collisions and binds to the next free port (e.g. 8001, 8002). Check the command prompt console for the active URL.

### 5. `ExecutionPolicy` Blocks Diagnostic Script
- **Cause**: Windows PowerShell default security restricts running unsigned scripts.
- **Fix**: `check_system.bat` already bypasses this with `-ExecutionPolicy Bypass`. If running manually via PowerShell, execute:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\check_system.ps1
  ```
