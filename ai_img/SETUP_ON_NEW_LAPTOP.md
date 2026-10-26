# Setup Guide for Fresh Windows Laptops

This guide explains how to run the **PS-05 AI Image Detection** forensic module on a brand-new Windows laptop that has **nothing installed** except Windows itself.

---

## 1. Minimum Laptop Requirements

| Requirement | Value | Why it's needed |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (version 1809+) or Windows 11 | Required for PowerShell 5.1 and modern Python support. |
| **Architecture** | **64-bit (x64)** | 32-bit Windows is not supported. |
| **Free Disk Space** | **15 GB or more** | Needed for Python libraries (PyTorch is ~2.5 GB) and AI models (~933 MB). |
| **Internet Connection** | **Required for first run only** | Downloads dependencies and model files. After setup, runs 100% offline. |
| **Administrator Rights** | Recommended | Allows `winget` to install Python and VC++ Redistributable automatically. |

---

## 2. Step-by-Step Instructions

### Step 1: Copy the Project Folder
Copy the entire `ai_img` folder onto the new laptop (e.g. to `C:\Forensics\ai_img` or your Desktop).
- If you copy the model files along with the project folder (`ai_image_detection\models\ViT-L-14.pt` and `fc_weights.pth`), the launcher will verify them and skip downloading them.
- If the model files are not copied, the launcher will download them automatically during setup.

### Step 2: (Optional) Run the Pre-Flight Diagnostic
Before launching, you can double-click:
```text
check_system.bat
```
This inspects your laptop in 3 seconds using built-in Windows commands and prints:
- Windows version and 64-bit support.
- Free disk space.
- Whether Python, VC++ runtime, or an NVIDIA GPU are present.
- Whether PyPI and model download servers are reachable.
- Integrity and size of existing model files.

### Step 3: Double-Click the Launcher
Double-click:
```text
run_platform.bat
```

### Step 4: What to Expect on First Run
1. **Prerequisite Check [1/7 & 2/7]:**
   - The launcher checks for 64-bit Windows and free disk space.
   - If Python 3.10 or Microsoft Visual C++ Redistributable is missing, the launcher will automatically install them silently using Windows Package Manager (`winget`).
2. **Virtual Environment [3/7]:**
   - Creates a dedicated, self-contained Python virtual environment (`.venv`) inside the folder.
3. **Dependency Installation [4/7]:**
   - Automatically detects whether an NVIDIA GPU is present (`nvidia-smi`).
   - Installs PyTorch (CUDA build if NVIDIA GPU is found, or CPU build otherwise).
   - Installs all locked Python packages.
   - Installs OpenAI CLIP directly from a clean archive (**no Git required**).
   - *Time:* Takes 3 to 8 minutes depending on your internet connection speed.
4. **Model Check [5/7]:**
   - Verifies the integrity of `ViT-L-14.pt` (932,768,134 bytes) and `fc_weights.pth` (4,083 bytes).
   - If missing, downloads them from verified official sources.
5. **Folder Setup & Launch [6/7 & 7/7]:**
   - Creates evidence folders (`uploads`, `artifacts`, `cache`).
   - Automatically selects an available port (from 8000 upward).
   - **Automatically opens your web browser** to the dashboard:
     ```text
     ==============================================
      PS-05 Digital Evidence Platform - AI Image Detection is running
      Open this link in your browser:
      http://127.0.0.1:8000/
      Press CTRL+C to stop the server
     ==============================================
     ```

### Step 5: Second and Subsequent Runs
Every subsequent run takes **under 2 seconds**. The launcher detects that all dependencies are installed, skips setup, and immediately launches the website.

---

## 3. Command-Line Options (For Advanced Users)

You can run `run_platform.bat` with optional flags from a Command Prompt:

- **Dry Run (Simulation mode):**
  ```cmd
  run_platform.bat /dryrun
  ```
  Inspects the system, prints exactly what would be installed, and exits without making any changes.
- **Clean Reset (Reinstall mode):**
  ```cmd
  run_platform.bat /reset
  ```
  Deletes `.venv` and dependency markers to force a fresh reinstall from scratch.
- **Non-Interactive Mode:**
  ```cmd
  run_platform.bat /nopause
  ```
  Prevents the batch file from pausing on exit (useful for automated scripts and tests).

---

## 4. Troubleshooting Table

| Problem / Error | Cause | Solution |
| :--- | :--- | :--- |
| **"winget is not recognized"** | Older Windows 10 build that lacks Windows Package Manager. | Install Python 3.10 manually from [python.org](https://www.python.org/downloads/release/python-31011/) (ensure you tick **"Add Python to PATH"**) and VC++ Redistributable from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe), then double-click `run_platform.bat` again. |
| **"Free disk space is below 10 GB"** | Target drive is running low on disk space. | Free up at least 10–15 GB on the drive where the project is located. |
| **"Dependency installation failed"** | Internet interrupted during PyTorch or wheel download. | Ensure your Wi-Fi is connected and run `run_platform.bat` again. The installer resumes from where it stopped. |
| **"CLIP checkpoint download failed"** | OpenAI Azure CDN was unreachable during initial setup. | Manually download `ViT-L-14.pt` from `https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt` and place it in `ai_image_detection\models\clip\ViT-L-14.pt`. |
| **"CUDA error: no kernel image is available"** | Newer laptop GPU (e.g. RTX 50-series) with unsupported compute capability. | No action required! The module's built-in automatic CPU fallback catches this immediately and completes forensic inference seamlessly on the CPU. |
| **Port already in use** | Another application is listening on default port 8000. | No action required! The launcher automatically scans ports 8000–8100 and assigns the first free port. |
