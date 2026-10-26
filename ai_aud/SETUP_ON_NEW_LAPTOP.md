# Operator Setup Guide: PS-05 Audio Forensics Platform

**Target Audience**: Forensic Analysts, Law Enforcement Officers, and System Integrators.  
**Prerequisite Experience**: None (Plain English, zero command-line expertise required).

---

## 1. Laptop Hardware & System Requirements

Before copying the project to a new laptop, ensure the machine satisfies these minimum specifications:

| Requirement | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (version 2004+) or Windows 11 | Windows 11 64-bit |
| **Architecture** | 64-bit (x64) strictly required | 64-bit (x64) AMD/Intel processor |
| **Free Disk Space** | 10 GB free on local C: drive | 20+ GB SSD free |
| **RAM** | 8 GB RAM | 16 GB RAM |
| **Graphics (GPU)** | Not required (runs on CPU) | NVIDIA GPU (RTX 3060+) for 4x faster analysis |
| **Internet Access** | Required **only** for initial setup (if models not copied) | Fully offline once setup completes |

---

## 2. Quick-Start Instructions (Double-Click Execution)

### Step 1: Copy the Project Folder
- Copy the entire `audio_forensics` folder onto the new laptop (e.g. into your `C:\Forensics\` or `C:\Users\Username\Documents\` folder).
- *Tip: If you copied the folder with `audio_forensics\models\xlsr2_300m.pt` and `LA_model.pth` already inside, you can run the setup 100% offline with no internet connection.*

### Step 2: Run the Automated Platform Launcher
1. Open the folder in Windows File Explorer.
2. Locate the file named **`run_platform.bat`**.
3. **Double-click `run_platform.bat`** (do not run as Administrator unless restricted by organization policy).

---

## 3. What to Expect on the First Run

When you double-click `run_platform.bat` for the first time, an automated console window will open and perform the following actions:

1. **System Health Inspection** (5 seconds):
   - Verifies 64-bit Windows architecture and available hard disk storage.
2. **Prerequisites Check & Automatic Installation** (1-3 minutes):
   - Checks for Python 3.10 and the Microsoft Visual C++ Runtime.
   - If either is missing, it will automatically install them silently using Windows Package Manager (`winget`).
3. **Environment Setup** (2-4 minutes):
   - Creates an isolated Python virtual environment (`.venv`) inside the folder.
   - Installs all forensic libraries and neural network components using pre-bundled local offline wheels.
4. **Model Checkpoint Verification** (instant if copied, ~10-15 minutes if downloading):
   - Verifies the integrity of the W2V2-AASIST deepfake neural network models (~5 GB total).
   - If missing, it downloads them directly with resume and retry capability.
5. **Server Launch**:
   - Finds an open local network port (defaulting to port `8000`).
   - Automatically opens your default web browser to the forensic dashboard:
     ```
     ==============================================
      PS-05 Audio Forensics is running
      Open this link in your browser:
      http://127.0.0.1:8000/
      Press CTRL+C to stop the server
     ==============================================
     ```

---

## 4. Normal Everyday Operation (Second Run Onward)

- On any subsequent run, all installations and checks are automatically skipped.
- Double-clicking `run_platform.bat` starts the server and opens the browser in **under 3 seconds**.
- The software runs **entirely locally on your laptop** — no cloud connections, no telemetry, and zero remote API calls.

---

## 5. Diagnostic Tool (`check_system.bat`)

If you want to verify that a laptop is ready before running the platform:
1. Double-click **`check_system.bat`**.
2. It will inspect Windows, storage, Python, VC++ runtime, network connectivity, and model weights, printing a simple status report.

---

## 6. Troubleshooting Table

| Symptom / Error Message | Likely Cause | Exact Solution |
| :--- | :--- | :--- |
| **Window closes immediately or flashes** | Batch error or permissions issue | Open Command Prompt (`cmd.exe`), navigate to folder with `cd /d "path"`, and run `run_platform.bat` to see the exact error. Check `logs\setup_YYYYMMDD_HHMMSS.txt`. |
| **`[ERROR] 64-bit Windows is strictly required`** | The laptop is running a 32-bit (x86) version of Windows | Deep learning frameworks (PyTorch and Fairseq) do not support 32-bit Windows. The laptop must be upgraded to 64-bit Windows. |
| **`Free disk space is below 10 GB`** | Insufficient storage on target drive | Clean temporary files or move the project to a drive with at least 10 GB of free space. |
| **`winget is not available on this machine`** | Older Windows 10 build (pre-App Installer) | Install Python 3.10 manually from: [python-3.10.11-amd64.exe](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe) (ensure you check **"Add Python to PATH"**), and Microsoft VC++ from [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe). Then double-click `run_platform.bat` again. |
| **`Model file incomplete or download failed`** | Internet interruption during large model download | Double-click `run_platform.bat` again (it will resume where it left off). Alternatively, manually place `xlsr2_300m.pt` and `LA_model.pth` into `audio_forensics\models\`. |
| **`Address already in use (port 8000)`** | Another application is using port 8000 | The launcher automatically searches for the next free port (8001, 8002, etc.). Look at the link printed in the console box. |
| **How to completely reset and reinstall?** | Damaged virtual environment or corrupted dependency | Double-click or run from command prompt: `run_platform.bat /reset`. It will cleanly delete `.venv` and reinstall everything. |
| **How to stop the platform?** | Server running in background or foreground | Press `CTRL+C` in the console window, or double-click `stop_platform.bat`. |
