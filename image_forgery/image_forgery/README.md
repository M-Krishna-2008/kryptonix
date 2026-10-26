# PS-05: Digital Evidence Authenticity and Integrity Verification Platform
## Forensic Module: `image_forgery`

A fully offline forensic module for detecting and localizing digital image tampering (splicing, copy-move duplication, object removal/inpainting, local retouching, and Photoshop manipulations). Designed for digital forensics units, law enforcement, and integrity verification laboratories.

> **Single Deep Engine Architecture**: Powered by **TruFor** (cross-modal transformer with RGB + Noiseprint++) corroborated by an independent suite of classical forensic checks (Metadata/EXIF, JPEG Quantization Analysis, Error Level Analysis, and SIFT/ORB Keypoint Matching).

---

## 1. Quick Start (Windows One-Click)

1. **Install Python 3.10+**: Download from [python.org](https://www.python.org/downloads/). *Important: check the box "Add Python to PATH" during installation.*
2. **Place TruFor Weights**:
   - Download `TruFor_weights.zip` (see [Section 4](#4-trufor-weights-setup) for details).
   - Extract and place `trufor.pth.tar` at:
     ```text
     models/trufor/trufor.pth.tar
     ```
3. **Double-click `run_windows.bat`**:
   - On the first run, it automatically creates `.venv`, detects GPU hardware, installs dependencies, logs setup to `setup.log`, and launches the application.
   - Subsequent runs skip setup and start in seconds.
4. **Open the Browser**:
   - Access the dashboard at the link printed in the terminal (default: `http://127.0.0.1:8000`).

---

## 2. Directory Structure

```text
image_forgery/
├── run_windows.bat           # One-click Windows batch launcher
├── run_linux.sh              # One-click Linux / WSL2 bash launcher
├── launch.py                 # Pure Python launcher with port fallback & status report
├── analyzer.py               # Core orchestrator: single analyze(file_path, options) entry point
├── router.py                 # FastAPI APIRouter prefix /api/image_forgery
├── schemas.py                # Pydantic v2 schemas adhering to standard contract
├── main_standalone.py        # Standalone FastAPI server for testing & UI mounting
├── requirements.txt          # Pinned dependencies with CUDA 12.8 instructions
├── README.md                 # System manual, equations, commands, and limitations
├── static/                   # Embedded & standalone UI (vanilla HTML/CSS/JS, no CDN)
│   ├── index.html            # Standalone web host
│   ├── module.js             # initModule(containerId) component
│   └── module.css            # Scoped styles (.image_forgery-*) with CSS variables
├── models/
│   ├── MANIFEST.json         # Checkpoint manifest (sha256, source url, license note)
│   └── trufor/               # Destination for trufor.pth.tar
├── engines/
│   ├── base.py               # BaseEngine abstract class & EngineOutput dataclass
│   ├── config.py             # Configurable thresholds with env var overrides
│   ├── classical.py          # Magic-byte validation, EXIF/XMP, JPEG quant, ELA, SIFT/ORB
│   ├── fusion.py             # TruFor binarization, classical corroboration, verdict rules
│   ├── trufor.py             # TruFor adapter
│   └── run_trufor.py         # Subprocess runner for TruFor (isolated memory execution)
├── third_party/
│   └── TruFor/               # Vendored TruFor repository and LICENSE.txt
└── tests/
    ├── samples/              # Synthetic test samples (authentic, spliced, copymove, etc.)
    ├── make_samples.py       # Sample image generator
    ├── run_tests.py          # Validation test suite checking schemas & vocabularies
    ├── benchmark.py          # Benchmark evaluator (AUC, F1, IoU, robustness mode)
    ├── test_live_server.py   # Live HTTP socket endpoint test
    └── test_launcher_e2e.py  # Launcher port-fallback and health verification test
```

---

## 3. Architecture & Deleted Components

Per direction, the module uses **TruFor** as the single deep-learning engine, supported by classical forensics.
The following items were removed:
- Deleted `engines/catnet.py` and `engines/run_catnet.py`.
- Deleted `engines/mvssnet.py` and `engines/run_mvssnet.py`.
- Deleted `models/catnet/` and `models/mvssnet/`.
- Deleted `third_party/catnet/` and `third_party/mvssnet/`.
- Removed `jpegio` dependency and other multi-engine overhead.
- Kept `engines/base.py` for extensible future adapter integration.

---

## 4. TruFor Weights Setup

### Official Source Details
- **Repository**: [grip-unina/TruFor](https://github.com/grip-unina/TruFor)
- **Official Download URL**: `https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip`
- **Expected Zip MD5**: `7bee48f3476c75616c3c5721ab256ff8`
- **Extracted File**: `trufor.pth.tar`
- **Target Destination**:
  ```text
  models/trufor/trufor.pth.tar
  ```
- **License**: Informational and nonprofit/research use only (see `third_party/TruFor/LICENSE.txt`).

> [!NOTE]
> **University Server Status**: The official university download host (`www.grip.unina.it`) frequently experiences connection timeouts on port 443 and misconfigured redirects (reported in GitHub Issues #31 and #35). If the automated download cannot connect, obtain `TruFor_weights.zip` and place `trufor.pth.tar` directly into `models/trufor/`.

---

## 5. Hardware & CUDA Setup (NVIDIA RTX 5060)

The target machine is a laptop with NVIDIA RTX 5060 (8 GB VRAM, Blackwell architecture). RTX 50-series GPUs require CUDA 12.8 or newer.

```powershell
# Windows (PowerShell)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Linux / WSL2 (Bash)
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

*(On machines without an NVIDIA GPU, PyTorch automatically runs in CPU fallback mode).*

---

## 6. Forensic Verdict & Confidence Rules

The module uses a single deep neural network (TruFor) corroborated by independent classical signals:

1. **`likely_tampered`**:
   - A TruFor anomaly region (area $\ge \text{min\_region\_area\_frac}$) with reasonable confidence that is **CORROBORATED** by at least one independent classical signal:
     - Overlapping Error Level Analysis (ELA) compression discrepancy,
     - Verified SIFT/ORB keypoint copy-move duplicate cluster,
     - EXIF embedded thumbnail mismatch,
     - Or medium/high metadata editing software traces (e.g. Adobe Photoshop).
   - Overall confidence is capped at **0.85**.
2. **`suspicious`**:
   - A TruFor region detected without classical corroboration, or classical anomalies present without neural localization, or weak contradictory signals.
   - Overall confidence is between **0.50 and 0.75**.
3. **`authentic`**:
   - TruFor ran, no suspicious region was detected, TruFor score $< 0.40$, no medium/high metadata findings, and reliability gating passed.
   - Worded: `"No evidence of manipulation found"`, never `"proven genuine"`.
   - Overall confidence is capped at **0.70** (reflecting that only one deep model was evaluated).
4. **`inconclusive`**:
   - Everything else, including corrupt files, non-images, tiny dimensions ($< 64\text{ px}$), or severe compression destruction.

---

## 7. Running the Platform

### Using the One-Click Launcher

**Windows**:
```cmd
run_windows.bat
```
Optional flags:
- `run_windows.bat --cpu`: Force CPU build of PyTorch.
- `run_windows.bat --reinstall`: Reset virtual environment and reinstall packages.

**Linux / WSL**:
```bash
chmod +x run_linux.sh
./run_linux.sh
```

### Manual Execution

```powershell
python launch.py --port 8000
```

### Running Test Suites

```powershell
# 1. Validation smoke tests (7/7 tests)
python tests/run_tests.py

# 2. Live HTTP socket API test
python tests/test_live_server.py

# 3. Launcher port-fallback and health check
python tests/test_launcher_e2e.py

# 4. Forensic dataset benchmark harness
python tests/benchmark.py --dataset-dir tests/samples/
```

---

## 8. Parent Dashboard Integration

To integrate `image_forgery` into the main PS-05 forensic website:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from image_forgery.router import router as image_forgery_router

app = FastAPI(title="PS-05: Digital Evidence Verification Platform")

# Mount API endpoints
app.include_router(image_forgery_router)

# Mount static UI assets
MODULE_STATIC = Path(__file__).parent / "image_forgery" / "static"
app.mount(
    "/image_forgery-static",
    StaticFiles(directory=str(MODULE_STATIC)),
    name="image_forgery-static"
)
```

In your dashboard template:
```html
<link rel="stylesheet" href="/image_forgery-static/module.css">
<div id="image-forgery-container"></div>
<script src="/image_forgery-static/module.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", () => {
    initModule("image-forgery-container");
  });
</script>
```
