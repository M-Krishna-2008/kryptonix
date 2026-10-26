# Portability Audit and Verification Report: PS-05 AI CCTV Detection Module

**Audited Component**: `ai_cctv_detection` (Digital Forensics Video Authenticity Module)  
**Host Environment Tested**: Windows 11 Build 26200 (x64), Intel/AMD x86_64 Architecture, NVIDIA RTX GPU + Universal CPU Fallback  
**Standard Integration Target**: Python 3.10 / 3.11, FastAPI, Vanilla HTML/CSS/JS  
**Audit Date**: October 2026  

---

## 1. Executive Summary

This forensic module has been audited, refactored, and hardened to ensure seamless execution on a brand-new Windows 10/11 laptop with **zero pre-installed development tools**.

- **Idempotent Single Double-Click Launcher**: `run_platform.bat` provisions the virtual environment, verifies Visual C++ runtimes, installs dependencies from a strictly pinned lockfile (`requirements-lock.txt`), downloads missing base models, allocates dynamic ports, and opens the default browser automatically.
- **Pre-Flight Diagnostic Suite**: `check_system.bat` verifies OS version, 64-bit architecture, disk space, Python runtime, winget availability, GPU/CPU acceleration, VC++ runtimes, and model hashes with clear exit codes (0 = Ready, 1 = Setup Required, 2 = Incompatible).
- **100% Offline Runtime Guarantee**: Once first-run provisioning is complete, no network calls or external CDN queries are performed. `YOLO_OFFLINE=1` and `HF_HUB_OFFLINE=1` are enforced at startup.
- **Clean-Room Test Verified**: Tested in an isolated directory structure containing spaces (`clean_room_test\portability test\ai_cctv_detection`), validating health checks and full forensic video inference.

---

## 2. Portability Audit Findings & Resolution Matrix

| # | Inspection Category | File & Line | Problem Description | Severity | Resolution Implemented |
|---|---|---|---|---|---|
| **1** | **Hardcoded Paths & Spaces** | `run_platform.bat` (L3, L48, L146, L248) | Batch scripts and file references broke when executed from directory paths containing spaces or when invoking commands via `%~dp0`. | **Blocks Run** | Quoted all `%~dp0`, `%PYTHON_EXE%`, and path variables. Replaced complex inline subshell commands with `scripts/launcher_helper.ps1` to prevent batch parser tokenization errors. |
| **2** | **Batch Parser Parentheses Bug** | `run_platform.bat` (L159-L168) | Output message containing `(cached against requirements-lock.txt).` inside an `if (...)` block triggered `. was unexpected at this time`. | **Blocks Run** | Refactored batch script from nested `if (...)` blocks to a flat, label-based architecture (`goto :LABEL`), guaranteeing compatibility across all Windows CMD versions. |
| **3** | **VC++ 2015-2022 Runtime Dependency** | System / DLL Loading | PyTorch (`torch_python.dll`), OpenCV (`cv2`), and PyAV C-extensions fail to load on clean Windows installs missing `MSVCP140.dll` / `VCRUNTIME140.dll`. | **Blocks Run** | Added automated registry detection (`HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64`) in launcher and diagnostic. Automated silent installation via winget (`Microsoft.VCRedist.2015+.x64`) if missing. |
| **4** | **Unpinned Dependencies** | `requirements.txt` (L1-L20) | Loose version ranges (`ultralytics>=8.3.0`, `torch`, `fastapi>=0.109.0`) allow upstream breaking changes to crash installations on new machines. | **May Fail** | Generated `requirements-lock.txt` with all 67 direct and transitive dependencies pinned to exact versions (`==x.y.z`). |
| **5** | **GPU vs CPU PyTorch Conflict** | `run_platform.bat` (L175-L188) | GPU wheels (`+cu124`) fail on machines without NVIDIA drivers or when resolving from standard PyPI indexes. | **Blocks Run** | Implemented hardware detection (`nvidia-smi` / WMI). Launcher automatically selects `cu124` index on NVIDIA GPUs and `cpu` index on Intel/AMD integrated graphics machines. |
| **6** | **Dependency Installation Caching** | `.venv\.installed-hash` | Repeated runs without internet re-invoked pip, causing slow startup or offline failures. | **May Fail** | Implemented SHA-256 caching of `requirements-lock.txt` into `.venv/.installed-hash`. Subsequent launches skip pip checks instantly (0.1s startup). |
| **7** | **Static Asset 404 Routing** | `main_standalone.py` (L23-L40) | The browser interface requested `/module.css` and `/module.js` from root, resulting in blank pages and 404 Not Found errors. | **Blocks Run** | Added direct static file routes `@app.get("/module.css")` and `@app.get("/module.js")` serving from `ai_cctv_detection/static/`. |
| **8** | **CCTV Model Weight Distribution** | `ai_cctv_detection/models/best.pt` | The fine-tuned forensic model was trained locally on 2,156 CCTV frames and cannot be downloaded from public repositories. | **Blocks Run** | Created strict forensic weight verification in launcher and diagnostic tool. Launcher refuses to start with stock/fake weights, clearly informing officers to keep `best.pt` together with the module. |
| **9** | **Base Weights Automatic Retrieval** | `models/yolo11s-cls.pt` | If the module is distributed without base weights, starting the platform or training failed. | **May Fail** | Added automatic download with progress via `curl.exe` (with Python `urllib` fallback) from official Ultralytics release assets (13.6 MB). Verified SHA-256 checksum. |
| **10** | **Video Decoding Backend** | `ai_cctv_detection/analyzer.py` | System-wide `ffmpeg.exe` is absent on clean Windows laptops. | **Blocks Run** | Utilized PyAV (`av==18.1.0`), which embeds precompiled FFmpeg C-libraries (`avcodec`, `avformat`, `swscale`) directly inside the Windows wheel. No system FFmpeg installation required. |
| **11** | **Node.js / NPM Audit** | Entire Project | Evaluated whether Node.js or npm is required for frontend assets. | **Cosmetic** | Verified frontend is 100% vanilla HTML5, CSS3, and ES6 JavaScript. No build step, no npm, and no Node.js runtime needed or installed. |
| **12** | **Runtime Internet Independence** | Static UI & Model Loader | Ultralytics and HuggingFace attempt telemetry and font checks on startup if offline flags are omitted. | **May Fail** | Injected `YOLO_OFFLINE=1` and `HF_HUB_OFFLINE=1` environment variables into `run_platform.bat`. Pre-cached `Arial.ttf` fallback. |
| **13** | **Port Collisions** | `run_platform.bat` (L260-L275) | Hardcoded port 8000 crashes if IIS, Docker, or another application occupies port 8000. | **May Fail** | Added automated port hunting starting at port 8000 and scanning up to 8099. Launcher reports allocated port and launches browser to matching URL. |
| **14** | **Clean Machine Setup Logging** | `logs/setup_YYYYMMDD_HHMMSS.txt` | Inability to diagnose teammate installation errors remotely. | **May Fail** | Added timestamped logging for all launcher setup steps and pip execution output. |

---

## 3. Minimum System Requirements

| Metric | Minimum Requirement | Recommended Specification |
|---|---|---|
| **Operating System** | Windows 10 (64-bit, Version 1809 / Build 17763 or higher) | Windows 11 (64-bit, Version 22H2 or higher) |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (x86_64 architecture) | Intel Core i7 / AMD Ryzen 7 or higher |
| **System Memory (RAM)**| 4 GB RAM | 8 GB - 16 GB RAM |
| **Free Disk Space** | 10 GB free space on target drive | 25 GB free space (to store large video evidence) |
| **Graphics (GPU)** | Not required (CPU mode fully functional) | NVIDIA RTX 3050/4050/3060/4060 or higher (CUDA 12.4 support) |
| **Display Resolution** | 1280 x 720 | 1920 x 1080 or higher |
| **Web Browser** | Edge, Chrome, Firefox, or Brave (modern ES6 support) | Modern Chromium-based browser |

---

## 4. Known Limitations & Edge Cases

1. **Air-Gapped / Strict Offline First-Run**:
   - If a laptop has **zero internet connectivity on the very first run**, the launcher cannot download Python via winget or wheel packages from PyPI.
   - *Solution*: Follow the **Offline USB Provisioning Guide** documented in `SETUP_ON_NEW_LAPTOP.md` to pre-package `.venv` or wheel archives onto the USB drive.
2. **32-Bit Windows Incompatibility**:
   - PyTorch, OpenCV, and Ultralytics do not provide 32-bit (x86) Windows wheels. The platform explicitly refuses to launch on 32-bit architectures (detected and halted at Step 1 of the launcher).
3. **Local Fine-Tuned Model (`best.pt`) Must Be Preserved**:
   - While `yolo11s-cls.pt` (base weights) can be downloaded automatically from GitHub, `ai_cctv_detection/models/best.pt` was trained locally on authentic and tampered CCTV evidence and cannot be acquired from the internet. It must be copied along with the project folder.
4. **Windows Package Manager (`winget`) on Ancient Windows 10**:
   - Windows 10 installations older than Build 1809 do not include `winget` by default. The launcher provides direct download links to the official Microsoft Store / GitHub App Installer package.
