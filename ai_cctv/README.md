# PS-05: AI CCTV Detection Module (`ai_cctv_detection`)

Part of **PS-05: Digital Evidence Authenticity and Integrity Verification Platform** (Digital Forensics track).  
Detects whether a CCTV video clip is authentic or AI-generated using fine-tuned YOLO11 classification on quality-gated frame tiles, aggregated temporally into clip-level forensic verdicts.

Runs **100% locally** (no external APIs or cloud calls at runtime) and maintains digital chain-of-custody via SHA-256 hashing.

---

## 1. Quick Start (Standalone Execution)

### Windows Quick Launcher
Double-click `run_platform.bat` or run:
```bat
run_platform.bat
```
This launcher automatically verifies Python 3.10/3.11, configures `.venv`, installs dependencies with GPU/CPU PyTorch auto-detection, checks base weights, allocates an open port, launches Uvicorn, and opens the browser.

### Manual Command Line
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run standalone server
uvicorn main_standalone:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.  
Interactive OpenAPI documentation: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**.

---

## 2. Parent Platform Integration Contract

To plug this module into the unified PS-05 dashboard app:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 1. Import module router
from ai_cctv_detection.router import router as cctv_router

app = FastAPI(title="PS-05 Digital Evidence Platform")

# 2. Mount module API router
app.include_router(cctv_router)

# 3. Mount static assets under unique module namespace
static_dir = Path("ai_cctv_detection/static")
app.mount("/ai_cctv_detection-static", StaticFiles(directory=str(static_dir)), name="ai_cctv_detection_static")
```

### Embedding UI in Dashboard
Include the CSS and JS in your main template, create a target container, and invoke `initModule`:
```html
<link rel="stylesheet" href="/ai_cctv_detection-static/module.css">
<div id="forensic-cctv-widget"></div>
<script src="/ai_cctv_detection-static/module.js"></script>
<script>
  initModule("forensic-cctv-widget");
</script>
```

---

## 3. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai_cctv_detection/analyze` | Multipart video upload (`file`). Streams up to 2 GB to disk, caches by SHA-256 + config hash, returns standard JSON result. Optional query params: `tracking=true` (ByteTrack), `job_id`. |
| `GET` | `/api/ai_cctv_detection/progress/{job_id}` | Real-time progress monitoring (`{stage: str, percent: int}`) for large video uploads. |
| `GET` | `/api/ai_cctv_detection/health` | Health check returning `{"status": "ok", "module": "ai_cctv_detection"}`. |
| `GET` | `/api/ai_cctv_detection/artifacts/{filename}` | Serves visual evidence artifacts (timeline plots and contact sheets). |

---

## 4. Pipeline Stages & Forensic Honesty

1. **Ingest & Chain of Custody**: Computes SHA-256 hash across the video stream; extracts codec, resolution, bitrate, fps, and duration using PyAV (with OpenCV fallback).
2. **Frame Sampling**: Extracts all I-frames (keyframes) plus ~2 fps uniform cadence, capped at 300 frames.
3. **Quality Gate**: Evaluates Laplacian blur variance ($\ge 60$ sharp, $< 20$ dropped), resolution, and compression blockiness.
4. **Native-Resolution Tiling**: Up to 4 crops of size $448 \times 448$ to preserve high-frequency sensor noise without destructive scaling.
5. **YOLO11 Classifier**: Ultralytics YOLO11-cls (`models/best.pt`).
   > **Forensic Honesty Rule**: Stock pretrained YOLO cannot detect AI video. If `models/best.pt` is missing, the module returns `inconclusive`, does NOT invent scores, provides an informative setup guide, and continues running metadata and quality screening.
6. **Platt Scaling**: Calibrates raw model logits using $(a, b)$ parameters from `configs/calibration.yaml`.
7. **Temporal Aggregation**: Computes quality-weighted median probability (`median_p`), fraction of AI frames (`frac_high`), and consecutive AI duration (`run_high`).
8. **Verdict Ladder**:
   - `quality < 0.30` or $< 8$ kept frames $\to$ `inconclusive`
   - `median_p >= 0.75` and `frac_high >= 0.60` $\to$ `likely_tampered` (Global AI)
   - `run_high >= 3.0s` and `frac_high >= 0.25` $\to$ `likely_tampered` (Splice)
   - `median_p <= 0.30` and `frac_high <= 0.10` $\to$ `authentic`
   - Otherwise $\to$ `inconclusive` (`suspicious` if $0.50 \le median\_p \le 0.75$)
9. **Visual Evidence Artifacts**: Generates `timeline.png` with highlighted suspicious spans and `contact_sheet.png` showing the 6 highest-scoring frames.

---

## 5. Model Training Protocol

See [TRAINING.md](file:///c:/Users/Grish%20ragav/Downloads/yolo%20project/TRAINING.md) for full instructions.
Run:
```bat
train_model.bat
```
This builds the dataset (split strictly by video source ID to prevent background leakage), verifies that metadata shortcuts do not exist, trains `yolo11s-cls`, and fits Platt scaling.
