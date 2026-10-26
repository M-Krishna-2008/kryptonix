# PS-05 Image Forgery Forensic Platform
## Quick Setup Guide for Brand-New Windows Laptops

This guide walks you through running the Image Forgery Forensic Platform on a brand-new Windows laptop (Windows 10 or Windows 11) with no developer tools pre-installed.

---

### Folder Overview & What to Double-Click

When you extract or copy the project folder to your laptop, it looks like this:

```text
image_forgery\
│
├── run_platform.bat      <--- DOUBLE-CLICK THIS TO START THE APP!
├── check_system.bat      <--- Double-click to run diagnostic audit only
│
├── models\
│   └── trufor\
│       └── trufor.pth.tar (Pre-trained neural weights, ~281 MB)
│
├── static\               (Offline Web UI: HTML, CSS, JavaScript)
├── tests\                (Automated test cases and sample images)
├── engines\              (TruFor model wrapper and forensics modules)
├── analyzer.py           (Forensics pipeline orchestrator)
├── launch.py             (Python orchestrator and server launcher)
├── requirements-lock.txt (Exact pinned dependency versions)
└── PORTABILITY_REPORT.md (Full portability audit and validation details)
```

---

### Option A: Fully Automated Setup (Recommended)
*Requires internet connection on first run only. Takes 5–12 minutes depending on your internet speed.*

1. **Copy or extract the `image_forgery` folder** onto your laptop (for example, into `C:\Forensics\image_forgery` or your Desktop).
2. **Double-click `run_platform.bat`**.
3. **What happens automatically:**
   - Detects Windows version, 64-bit architecture, and free disk space.
   - Checks if Python 3.10+ is installed. If missing, it installs Python 3.10 automatically via Windows Package Manager (`winget`).
   - Checks if Visual C++ Runtime is installed. If missing, it installs it automatically.
   - Sets up an isolated virtual environment (`.venv`).
   - Detects your graphics card:
     - If you have an NVIDIA GPU, it installs PyTorch with GPU hardware acceleration.
     - If no NVIDIA GPU is detected, it automatically installs PyTorch CPU mode.
   - Installs all required forensic libraries from `requirements-lock.txt`.
   - Checks the TruFor AI weights (`trufor.pth.tar`). If not present, it automatically downloads them from the official verified mirror.
   - Starts the server and opens your default web browser to:
     `http://127.0.0.1:8000`
4. **Second run:** On subsequent launches, setup is skipped completely and the application opens in **under 2 seconds**.

---

### Option B: 100% Offline Setup
*For air-gapped forensic labs or machines without internet access.*

1. On an internet-connected machine:
   - Ensure the weights file `models\trufor\trufor.pth.tar` is inside the folder (281,496,429 bytes).
   - In a PowerShell or CMD window inside the project folder, pre-download the wheels by running:
     ```cmd
     pip download -r requirements-lock.txt -d wheelhouse
     pip download torch torchvision -d wheelhouse
     ```
2. Copy the entire `image_forgery` folder (including `wheelhouse\` and `models\`) to the offline laptop via USB drive.
3. Install Python 3.10+ and Visual C++ Redistributable (installers can be copied on the USB drive):
   - Python: [python-3.10.11-amd64.exe](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe) (Tick "Add python.exe to PATH")
   - Visual C++: [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)
4. Double-click `run_platform.bat`. The launcher operates completely offline without contacting external networks.

---

### Flags and Command Line Options

For advanced users or troubleshooting, you can open Command Prompt in the folder and pass flags:

| Flag | Purpose |
| :--- | :--- |
| `run_platform.bat /dryrun` | Audit the laptop without installing anything. Reports pass/fail for every requirement. |
| `run_platform.bat /reset` | Deletes `.venv` and cache markers, forcing a clean re-installation. |
| `run_platform.bat --cpu` | Forces PyTorch CPU mode even if an NVIDIA GPU is present. |
| `run_platform.bat --port 8080` | Specifies a custom TCP port to run the web interface on. |

---

### Troubleshooting Matrix

| Issue / Error Message | Root Cause | Solution |
| :--- | :--- | :--- |
| **"Windows protected your PC" (SmartScreen)** | Windows flags unrecognized batch files copied from USB or downloads. | Click **"More info"**, then click **"Run anyway"**. |
| **"Python was not detected and winget is unavailable"** | Windows 10 prior to build 19041 or winget is disabled. | Download and install Python 3.10 manually from [python.org](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe). **Critical**: Check the box **"Add python.exe to PATH"**. |
| **"vcruntime140.dll missing"** | Visual C++ Redistributable 2015–2022 is not installed on Windows. | Download and install the official runtime from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe). |
| **"Port 8000 is busy"** | Another service is using port 8000. | The platform **automatically switches to port 8001, 8002, etc.** without failing. You can also specify `--port <number>`. |
| **"No NVIDIA GPU detected"** | Machine has Intel, AMD, or no discrete GPU. | **No action needed.** The application automatically switches to CPU mode and completes all analyses. |
| **"Filename too long / Path too long"** | Deep nested directories exceeding Windows 260-char path limit. | Move the `image_forgery` folder closer to drive root (e.g., `C:\Forensics\image_forgery`). |
| **Flaky or interrupted connection during setup** | Connection dropped while downloading wheels or model weights. | Re-run `run_platform.bat`. The launcher safely resumes partial downloads from where they stopped. |
