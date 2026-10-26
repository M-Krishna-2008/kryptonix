# PS-05 Unified AI Forensics Platform

A unified local AI forensics web application and one-click launcher integrating four state-of-the-art forensic modules behind a single interface:
1. **`ai_aud` (Audio Forensics)**: Acoustic authenticity verification and speech deepfake detection using Wav2Vec2/XLS-R 300M representations and an AASIST spectral graph attention network.
2. **`ai_img` (AI Image Detection)**: AI-generated synthetic image detection (Universal Fake Detect) via frozen CLIP ViT-L/14 visual backbone and a calibrated linear probe.
3. **`image_forgery` (Photoshop Tamper Localization)**: Pixel-level image tampering, splicing localization, and copy-move detection using TruFor cross-modal deep transformer, Error Level Analysis (ELA), and EXIF metadata consistency checks.
4. **`ai_cctv` (CCTV Video Forensics)**: CCTV video AI tampering & synthetic frame detection utilizing a locally fine-tuned YOLO11s classifier, temporal windowing, native 224x224 tile analysis, and Platt probability scaling.

Built with a **Claude-inspired warm minimalist aesthetic**, 100% local vanilla web technologies (HTML5, CSS custom properties, ES modules, Canvas), and an asynchronous Python gateway that reverse-proxies all four backends. **Zero Node.js, zero build steps, zero CDN dependencies — 100% offline capable.**

---

## 3-Step Quick Start

```cmd
git clone <repo-url>
cd <repo-folder>
run.bat
```

1. **Clone or Download ZIP**: Clone the repository or extract the release archive onto any Windows 10/11 64-bit PC.
2. **Double-click `run.bat`**: The root launcher automatically provisions the Python environment, downloads missing model weights with hash verification and resume, creates required runtime folders, allocates free ports, and starts all four backends in the background.
3. **Open the Single Link**: The launcher automatically opens `http://localhost:8080` in your default browser once health checks turn green.

To stop all services cleanly at any time, double-click `stop.bat`.

---

## Minimum System Requirements

| Prerequisite | Minimum Specification | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 or 11 (64-bit) | Strictly required by PyTorch and compiled neural backends |
| **Python** | Python 3.10 (64-bit) | Auto-detected; auto-provisioned via `winget` if missing |
| **Internet Connection** | Required for first run only | Downloads dependencies and model checkpoints; 100% offline afterwards |
| **Free Disk Space** | ~15 GB recommended | 6.3 GB model downloads + virtual environment + temporary cache |
| **Download Size** | ~6.3 GB total | XLS-R (3.6 GB), LA_model (1.2 GB), CLIP ViT-L/14 (890 MB), TruFor (281 MB), YOLO base (13 MB) |
| **System RAM** | 8 GB minimum (16 GB recommended) | Accommodates large neural model inference |
| **GPU (Optional)** | NVIDIA GPU (CUDA 11.8+ / 12.1+) | Auto-detected. Clean CPU fallback supported on all modules. |
| **Node.js / npm / Build Tools** | **NOT REQUIRED** | Frontend is vanilla ES6/CSS; zero build steps needed |

---

## Launcher Options & Flags

`run.bat` supports standard flags:
```cmd
:: Dry-run mode: inspects system, verifies models manifest, checks ports, prints execution plan
run.bat /dryrun

:: Setup mode: downloads models, sets up virtualenv and dependencies without launching servers
run.bat /setup

:: Reset mode: terminates any running background services, cleans runtime state, and exits
run.bat /reset

:: Headless mode: starts services without automatically opening the browser
run.bat /nobrowser
```

---

## Offline Deployment (Air-Gapped Workstations)

For environments without internet access:
1. Run `make_offline_bundle.bat` on an internet-connected workstation. This scripts bundles code, UI assets, and all downloaded model checkpoints into `..\PS05_Offline_Bundle`.
2. Transfer the folder or generated `.zip` via USB to the target air-gapped PC.
3. On the target PC, double-click `run.bat`. The launcher verifies existing model hashes and starts immediately without requesting external network resources.

---

## Architecture Overview

```
                        ┌──────────────────────────────────────────────┐
                        │              Browser (Client)                │
                        │         http://localhost:8080                │
                        └──────────────────────┬───────────────────────┘
                                               │ (Same-Origin / No CORS)
                        ┌──────────────────────▼───────────────────────┐
                        │            Unified Gateway Server            │
                        │   (FastAPI • Static Host • Async Jobs)      │
                        └───┬─────────────┬─────────────┬───────────┬──┘
                            │             │             │           │
        ┌────────────────────┘             │             │           └────────────────────┐
        ▼                                  ▼             ▼                                ▼
 ┌──────────────┐                 ┌──────────────┐ ┌──────────────┐               ┌──────────────┐
 │    ai_aud    │                 │    ai_img    │ │image_forgery │               │   ai_cctv    │
 │  Port: 8001  │                 │  Port: 8002  │ │  Port: 8003  │               │  Port: 8004  │
 │ XLS-R+AASIST │                 │ UnivFD CLIP  │ │ TruFor + ELA │               │ YOLO11 Video │
 └──────────────┘                 └──────────────┘ └──────────────┘               └──────────────┘
```

* **Single Origin**: All interactions occur via `http://localhost:8080`. APIs and artifacts are dynamically proxied under `/api/aud/*`, `/api/img/*`, `/api/forgery/*`, and `/api/cctv/*`.
* **Dynamic Free Port Allocation**: Avoids port conflicts by dynamically identifying free local TCP ports and writing them to [`runtime/ports.json`](file:///runtime/ports.json).
* **Asynchronous Execution Queue**: Long-running video and audio analyses are dispatched asynchronously with live polling for progress percentage and intermediate stages.

---

## Forensic Metrics & Interpretation

1. **Audio Forensics (`ai_aud`)**:
   - Primary metric: **Bona-Fide Logit** (higher values indicate authentic human speech).
   - *Forensic Rule*: This metric is an uncalibrated acoustic logit, never a percentage or probability.
2. **AI Image Detection (`ai_img`)**:
   - Primary metric: **Calibrated P(fake)** (0.0% to 100%).
   - Displays 9-crop spatial variation and Laplacian sharpness indicators.
3. **Photoshop Forgery Localization (`image_forgery`)**:
   - Displays **TruFor Transformer integrity score** (0.0 = authentic, 1.0 = tampered).
   - Side-by-Side and Opacity Overlay viewers visualize localized tampering heatmaps.
4. **CCTV Video Forensics (`ai_cctv`)**:
   - Interactive timeline chart displaying median frame anomaly scores over time with a 0.70 threshold.
   - Click-to-Seek video player automatically seeks to flagged anomaly timestamps.

> **Forensic Caution Notice**:
> *"Forensic tool outputs constitute investigative indicators, not definitive legal proof. Outputs must always be corroborated with DVR logs, physical camera hardware, original bitstream hashes, and a documented chain of custody."*

---

## Troubleshooting Guide

| Issue | Likely Cause | Solution |
| :--- | :--- | :--- |
| **Port Conflict (e.g. 8080 in use)** | Another service is using port 8080. | The launcher automatically searches and binds the next available port. Check console output or `runtime\ports.json`. |
| **Model download interrupted** | Network disruption during download. | Re-run `run.bat`. The launcher natively resumes downloads (`curl -C -`) and verifies the SHA-256 hash before use. |
| **Module shows "Down" or red indicator** | Missing model file or dependencies. | Review `logs\<module>_stderr.log` for details. Refer to `models\MODELS.json` for manual placement instructions. |
| **"Signature not recognized" (HTTP 400)** | File header mismatch or invalid magic bytes. | The gateway inspects file magic bytes. Ensure uploaded files are genuine media files, not renamed text or corrupted payloads. |
| **PowerShell ExecutionPolicy error** | Script execution restricted by Windows policy. | `run.bat` automatically invokes PowerShell with `-ExecutionPolicy Bypass`. If running manually, run `powershell -ExecutionPolicy Bypass -File scripts\launch.ps1`. |

---

## Licenses & Attributions

See [`LICENSE_NOTES.md`](file:///LICENSE_NOTES.md) for full attribution details:
* **Ultralytics YOLO11**: GNU AGPL-3.0
* **Meta AI Fairseq / XLS-R**: CC-BY-NC 4.0
* **W2V2-AASIST**: ASVspoof Research License / MIT
* **OpenAI CLIP**: MIT License
* **Universal Fake Detect**: MIT License
* **TruFor**: Nonprofit / Research and Forensic Evaluation License (GRIP Unina)
* Pretrained weights over 25 MB and raw datasets are not redistributed in this repository.
