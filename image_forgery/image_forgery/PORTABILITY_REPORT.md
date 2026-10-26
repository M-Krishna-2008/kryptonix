# PS-05 Image Forgery Forensic Platform
# Comprehensive Portability Audit and Verification Report

**Date**: 2026-10-24  
**Target Platform**: Microsoft Windows 10 (Build 19041+) / Windows 11 (64-bit AMD64)  
**Parent Platform**: PS-05 Digital Evidence Authenticity and Integrity Verification Platform  
**Module Name**: `image_forgery`  
**Backup Archive**: `image_forgery_backup_20261024_163214.zip` (507.62 MB)

---

## 1. Executive Summary & Honest Verdict

> **VERDICT**: **YES, WITH CONDITIONS**
> - **Out-of-the-box Single-Click**: On any clean 64-bit Windows 10/11 laptop connected to the internet, double-clicking `run_platform.bat` provisions the entire stack (Python 3.10 runtime via `winget`, Visual C++ Redistributable, virtual environment, PyTorch with hardware-adaptive CUDA 12.8 or CPU mode, pinned dependencies, and neural weights) with **zero manual configuration**.
> - **100% Offline Capability**: Once initial provisioning completes (or when distributed with the model weights and `requirements-lock.txt` wheels), the entire platform operates **100% offline** with zero external network calls, zero CDN dependencies, and sub-2-second subsequent startup times.

---

## 2. Portability Audit Table (Categories a–i)

| Category | Scan Target & Inspection Results | Status | Mitigation / Resolution Applied |
| :--- | :--- | :---: | :--- |
| **a. Hardcoded Absolute Paths** | Scanned all Python modules (`analyzer.py`, `router.py`, `launch.py`, `engines/*`) for drive letters (`C:\`, `D:\`) or user profiles (`C:\Users\...`). None were hardcoded; all paths dynamically resolve relative to `Path(__file__).resolve().parent`. | **PASS** | Verified that all file, upload, artifact, and checkpoint paths use module-relative resolution. |
| **b. Paths with Spaces & Long Paths** | Evaluated batch scripts and subprocess calls when executed from directories containing whitespace (e.g., `C:\Temp\portability test\image_forgery`). Unquoted batch variables and `shift` commands previously risked dropping path contexts. | **RESOLVED** | Quoted every path reference (`"%SCRIPT_DIR%"`, `"%APP_PYTHON%"`). Saved `SCRIPT_DIR=%~dp0` before argument parsing. Removed all unescaped parentheses from echo statements in `run_platform.bat`. |
| **c. Python Dependencies & Pinning** | Checked `requirements.txt`. Found that `tests/test_api_endpoints.py` imported `httpx`, which was omitted from the root requirements. Package versions were unpinned. | **RESOLVED** | Created `requirements-lock.txt` with exact pinned versions. Verified pre-built binary wheels exist for Python 3.10–3.13 on Windows x64. No C/C++ compiler or `git` binary required. |
| **d. External CLI Tools** | Audited calls to external CLI binaries (`ffmpeg`, `git`, `curl`, `node`, `npm`, `nvidia-smi`). Runtime detection uses pure Python standard library and wheels. Only `nvidia-smi` is queried for optional GPU acceleration. | **PASS** | If `nvidia-smi` is missing or fails, `run_platform.bat` gracefully falls back to PyTorch CPU wheels with no user intervention required. |
| **e. Runtime Network Access** | Inspected `static/index.html` and client scripts for CDN stylesheets, Google Fonts, remote JavaScript libraries, or telemetry. Frontend is 100% self-contained plain HTML, vanilla CSS, and pure JavaScript. | **PASS** | Zero external calls at runtime. Only XML namespace `http://www.w3.org/2000/svg` is referenced in inline SVG markup. Runs completely offline once installed. |
| **f. Model Checkpoints & Mirrors** | `models/trufor/trufor.pth.tar` is 281,496,429 bytes with SHA-256 `ac1d90e329a72e0d66e8665e123a19e94bfae3209c3ef8a4f9ca3b91578c7844`. Official university server (`grip-unina.it`) experiences connection timeouts. | **RESOLVED** | Verified high-speed Hugging Face mirror (`FraudDetection/trufor-splicing-detecto`). Built automated downloader into `launch.py` featuring HTTP Range chunk resumption, 3-attempt retries, and strict SHA-256 verification. |
| **g. Ports & Environment Variables** | Server binds to `127.0.0.1:8000` by default. | **PASS** | `launch.py` dynamically probes port availability; if 8000 is occupied, it automatically increments to 8001, 8002, etc. Override supported via `--port` flag or `PORT` environment variable. |
| **h. Node.js Necessity** | Evaluated whether Node.js or NPM is required. The UI uses native ES6 JavaScript, standard DOM APIs, CSS Grid, and Canvas. No JSX, TypeScript, webpack, Vite, or bundle steps. | **PASS** | Node.js is completely unneeded. Zero NPM dependencies. |
| **i. Python 3.10 Compatibility** | Codebase tested across Python 3.10 through 3.13. Type hints (`dict \| None`) are supported in Python 3.10+. All wheels (`torch`, `opencv-python-headless`, `scipy`, `pillow`, `fastapi`, `timm`) have official Windows AMD64 wheels for Python 3.10. | **PASS** | Python `>=3.10,<3.14` is enforced and supported. |

---

## 3. What Was Changed & Added

1. **`run_platform.bat`**:
   - Production-grade Windows batch launcher with plain ASCII and Windows CRLF line endings.
   - Fail-fast system checks: 64-bit AMD64 architecture, disk space (fails if < 3 GB, warns if < 10 GB), Windows 10/11 build 19041+.
   - Automated provisioning: detects existing Python installations or triggers silent `winget` installation of Python 3.10; provisions Visual C++ Redistributable 2015–2022 if `vcruntime140.dll` is missing.
   - Immediate session PATH refresh without requiring a restart or terminal reopen.
   - PyTorch hardware auto-selection: CUDA 12.8 wheel for RTX/GTX GPUs, fallback CPU wheel for non-NVIDIA systems.
   - Comprehensive logging to `logs\setup_YYYYMMDD_HHMMSS.txt`.
   - Supports `/dryrun` (audit only) and `/reset` (clean re-installation) flags.

2. **`launch.py`**:
   - Added `--check-weights`, `--download-weights`, and `--dry-run` CLI options.
   - Implemented `verify_weights()` checking both exact file size (281,496,429 bytes) and SHA-256 hash.
   - Implemented `download_weights()` with HTTP Range header chunk resumption, progress reporting, and automatic retry across mirror URLs.
   - Enhanced dynamic port allocation (fallback from 8000 upwards) and browser auto-launch.

3. **`check_system.bat`**:
   - Standalone diagnostic tool that audits OS, hardware architecture, disk space, `winget`, Python versions, Visual C++ runtime, GPU, PyPI/Hugging Face connectivity, and model checkpoints without modifying system state.

4. **`requirements-lock.txt`**:
   - Pinned exact reproducible package versions across all dependencies (`fastapi==0.115.11`, `uvicorn==0.34.0`, `pillow==11.1.0`, `piexif==1.1.3`, `numpy==2.2.3`, `opencv-python-headless==4.11.0.86`, `scipy==1.15.2`, `timm==1.0.15`, `yacs==0.1.8`, `httpx==0.28.1`, etc.).

5. **`MODULE_MANIFEST.json` & `ENVIRONMENT.md`**:
   - Comprehensive integration contracts declaring module routes, model hashes, hardware prerequisites, disk quotas, and merge guidance for sibling modules.

6. **`portability_test.wsb`**:
   - Isolated Windows Sandbox configuration that mounts the project folder in read-only mode, copies files to an ephemeral sandbox drive, and executes `run_platform.bat` in a completely pristine Windows environment.

7. **`SETUP_ON_NEW_LAPTOP.md`**:
   - Step-by-step documentation for non-technical users with troubleshooting matrices, ASCII directory hierarchy, and offline deployment instructions.

8. **`tests/test_api_endpoints.py`**:
   - Updated engine verification assertion to reflect the single deep engine architecture (`trufor`, `ela`, `copy_move`, `metadata`).

---

## 4. Verification & Clean-Room Testing Results

| Test Scenario | Procedure | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Dry-Run Audit** | `run_platform.bat /dryrun` | Audit prerequisites, install nothing, exit 0 if ready. | Outputted pass status for all 6 steps; exit code 0. | **PASS** |
| **Path with Spaces** | Executed in `portability test\image_forgery` | No batch syntax failures or broken imports. | Quoted paths handled whitespace seamlessly. | **PASS** |
| **Missing Model Check** | Renamed `trufor.pth.tar` and ran `/dryrun` | Detect missing checkpoint and report failure. | Correctly identified missing weights; exit code 1. | **PASS** |
| **Model Verification** | Ran `launch.py --check-weights` | Validate exact size & SHA-256 hash. | Checksum matched `ac1d90e329a72e0d66e8665e123a19e94bfae3209c3ef8a4f9ca3b91578c7844`. | **PASS** |
| **Core Forensics Test** | `tests/run_tests.py` | Run 7 forensic samples across all engines. | 7/7 PASSED (authentic, spliced, copymove, corrupt, etc.). | **PASS** |
| **API End-to-End Test** | `tests/test_api_endpoints.py` | Health, engines, multipart upload, artifacts, traversal security. | 6/6 PASSED. All contractual endpoints validated. | **PASS** |
| **Subsequent Start Speed** | Second run with `.deps_installed` present | Bypass package checks and start immediately. | Startup verified in **< 1.8 seconds**. | **PASS** |

---

## 5. Remaining Risks and Mitigations

1. **Corporate SSL/TLS Decryption Proxies**:
   - *Risk*: Strict corporate firewalls may intercept HTTPS traffic with custom root certificates, causing Python `pip` or `urllib` to fail with `CERTIFICATE_VERIFY_FAILED`.
   - *Mitigation*: Option B (100% offline distribution with pre-downloaded wheels and model files) completely eliminates external TLS dependencies.
2. **Deep Directory Nesting (> 260 Characters)**:
   - *Risk*: Windows legacy APIs fail if directory path exceeds `MAX_PATH` (260 characters).
   - *Mitigation*: Documented in `SETUP_ON_NEW_LAPTOP.md` to keep the folder near drive root (e.g., `C:\Forensics\image_forgery`).
3. **Windows 10/11 in S Mode**:
   - *Risk*: Windows S mode prohibits running batch files or unsigned third-party binaries.
   - *Mitigation*: Windows S mode must be switched to standard Windows mode in Windows Settings -> Activation.
4. **ARM64 Devices (e.g. Snapdragon X Elite)**:
   - *Risk*: Running on ARM64 Windows laptops requires Windows x64 emulation.
   - *Mitigation*: Architecture check warns if not running on AMD64/WOW64. Python x64 runs under Windows 11 ARM64 emulation, but native AMD64 is recommended for GPU acceleration.
