# PS-05 Audio Forensics Module

## Overview
The `audio_forensics` module is a fully local, explainable audio authenticity and integrity verification system built for law enforcement, digital forensics units, and intelligence analysts. It operates 100% locally with zero cloud dependencies at inference time.

The module incorporates:
1. **W2V2-AASIST Neural Anti-Spoofing Model**: Combines Facebook Fairseq's multilingual Wav2Vec 2.0 (XLS-R 300M) transformer front-end with an AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks) back-end to detect AI-generated, synthetic, and vocoded voice deepfakes.
2. **Signal-Processing Splice & Tampering Heuristics**: Lightweight explainable checks detecting background noise floor discontinuities, spectral flux change points, segment repetition (copy-paste), and bandwidth discrepancies.
3. **Forensic Chain-of-Custody**: Computes cryptographic SHA-256 hashes of all analyzed evidence files.
4. **Interactive Visual Evidence**: Generates synchronized waveforms with shaded suspicious regions, log-spectrograms with cut-point markers, and per-window logit timelines.

---

## Model Architecture & Score Interpretation
- **Architecture**: Published W2V2-AASIST (Tak et al., Odyssey 2022, arXiv:2202.12233).
- **Front-end**: Wav2Vec 2.0 XLS-R 300M self-supervised transformer extracting 1024-dimensional contextual representations.
- **Back-end**: Heterogeneous Stacking Graph Attention Layer (HS-GAL) with spectral and temporal subgraphs and top-k graph pooling.
- **Score Direction (VERIFIED)**:
  - The raw output is the **bona-fide logit** (index 1 of the AASIST output layer).
  - **Higher logit = Genuine / Authentic speech**.
  - **Lower logit = Spoofed / AI-generated / Synthetic speech**.
  - Raw scores are **logits**, NOT probability percentages. Never interpret a logit of +2.5 as "25%".
- **Thresholds & Uncertain Band**:
  - `low_threshold` (default `-1.5`): Scores below this indicate strong synthetic speech characteristics.
  - `high_threshold` (default `+1.5`): Scores above this indicate natural acoustic speech.
  - `[-1.5, +1.5]`: Uncertain band requiring contextual human examiner corroboration.

---

## Directory Structure
```
audio_forensics/
├── __init__.py           # Package exports
├── config.py             # System paths, constants, threshold loader
├── schemas.py            # Pydantic schemas adhering to Standard Result Format
├── audio_preprocess.py   # Resampling (16 kHz), mono conversion, 64,600-sample windowing
├── model_aasist.py       # W2V2-AASIST architecture and model singleton
├── heuristics.py         # Signal-processing splice checks
├── visualizer.py         # Headless plotting for waveform, spectrogram, and timeline
├── analyzer.py           # Core entry point analyze(file_path, options) -> dict
├── router.py             # FastAPI APIRouter prefix "/api/audio_forensics"
├── configs/
│   └── thresholds.yaml   # Calibrated score boundaries
├── static/
│   ├── index.html        # Standalone landing page
│   ├── module.js         # initModule(containerId)
│   └── module.css        # Scoped .audio_forensics- stylesheet
├── models/               # xlsr2_300m.pt, LA_model.pth
├── tests/                # Pytest test suite & sample generator
└── README.md
```

---

## Running Standalone
### Option 1: Automated Windows Launcher (Recommended)
Double-click `run_platform.bat` in the repository root. The script idempotently:
1. Validates Python 3.10 / 3.9.
2. Initializes the virtual environment `.venv`.
3. Installs dependencies and checks for CUDA GPU acceleration.
4. Checks and downloads model weights if missing.
5. Launches the platform on an available port (e.g. `http://127.0.0.1:8000/`) and opens the browser.

### Option 2: Manual Command Line
```powershell
# Activate your Python 3.10 virtual environment
.\.venv\Scripts\activate

# Launch standalone server
uvicorn main_standalone:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to:
- Standalone UI: `http://127.0.0.1:8000/`
- Interactive API Documentation: `http://127.0.0.1:8000/docs`

---

## Integration into Parent Platform
To embed this module into the master PS-05 Digital Evidence Verification Platform:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 1. Import router and static path from audio_forensics
from audio_forensics.router import router as audio_router
from audio_forensics.config import STATIC_DIR as AUDIO_STATIC_DIR

app = FastAPI(title="PS-05 Digital Evidence Platform")

# 2. Mount API endpoints under /api/audio_forensics
app.include_router(audio_router)

# 3. Mount static assets under /audio_forensics-static
app.mount(
    "/audio_forensics-static",
    StaticFiles(directory=str(AUDIO_STATIC_DIR)),
    name="audio_forensics_static",
)
```

In the master dashboard HTML:
```html
<link rel="stylesheet" href="/audio_forensics-static/module.css" />
<div id="audio-module-container"></div>
<script src="/audio_forensics-static/module.js"></script>
<script>
  initModule("audio-module-container");
</script>
```

---

## Core Function Signature
`analyzer.py` exposes:
```python
def analyze(file_path: str, options: dict | None = None) -> dict
```
It returns the **Standard Result Format** JSON dictionary and never raises an exception to the caller.

---

## Threshold Calibration
To calibrate the detection thresholds for your specific deployment acoustic domain:
```powershell
.\.venv\Scripts\python.exe tools/calibrate.py data_audio/bonafide data_audio/spoof --save
```
This computes the Equal Error Rate (EER), ROC-AUC, and operating points at 5% FAR / 5% FRR, updating `audio_forensics/configs/thresholds.yaml`.
