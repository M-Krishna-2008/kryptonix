# Module Inspection & Forensic Specifications

This document catalogs the 4 sibling forensic modules inspected directly on the local system, including endpoints, method types, parameter schemas, response data shapes, verified runtimes, and model configurations.

---

## 1. `ai_aud` (Audio Forensics & Anti-Spoofing)

- **Purpose**: Local Speech Authenticity, Tampering & Deepfake Detection. Evaluates speech using Wav2Vec2/XLS-R 300M front-end and W2V2-AASIST graph-attention spectral acoustic back-end.
- **Root Directory**: `ai_aud`
- **Default Port**: `8001` (internal)
- **Python Version**: `3.10.11` (strict fairseq 0.12.2 compatibility, NumPy 1.26.4 pinned)
- **Entry Point**: `main_standalone:app` (FastAPI)
- **Model Files**:
  - `ai_aud/audio_forensics/models/xlsr2_300m.pt` (3.80 GB, SHA-256: `b08927597f2c9eb2ebd7dcc3ac78ee4b5f6021cbac4b3a6c5a9deec445d80ed9`)
  - `ai_aud/audio_forensics/models/LA_model.pth` (1.27 GB, SHA-256: `bd6f36097259fe54e7004eb983651e5304d807be81156dbd04faccb70d91e10c`)
- **Endpoints**:
  - `GET /api/audio_forensics/health` -> `{"status": "ok", "module": "audio_forensics"}`
  - `POST /api/audio_forensics/analyze`:
    - Method: `POST`
    - Form Field: `file` (`UploadFile`, multipart/form-data)
    - Max size: `MAX_UPLOAD_BYTES` (default 500 MB)
  - `GET /api/audio_forensics/progress/{job_id}` -> `{"job_id": str, "stage": str, "percent": int}`
  - `GET /api/audio_forensics/artifacts/{filename}` -> PNG / audio visual evidence
- **Key Forensic Rule**:
  - Raw metric: `bona_fide_logit` (higher = more genuine/authentic).
  - **CRITICAL**: The score is an uncalibrated logit, NOT a probability. It is NEVER displayed as a percentage or probability.
  - Verdicts: `authentic`, `suspicious`, `tampered`, `inconclusive`.
- **Verified Benchmark Run Time**: ~27 seconds (cold load) / ~17 seconds inference on CPU for a 10.4s audio clip.

---

## 2. `ai_img` (Universal Fake Detect Image Forensics)

- **Purpose**: AI-Generated Image & Synthesis Artifact Detection. Uses frozen CLIP ViT-L/14 backbone with a trained linear probe classifier.
- **Root Directory**: `ai_img`
- **Default Port**: `8002` (internal)
- **Python Version**: `3.13` (compatible with 3.10+)
- **Entry Point**: `main_standalone:app` (FastAPI)
- **Model Files**:
  - `ai_img/ai_image_detection/models/clip/ViT-L-14.pt` (932 MB, SHA-256: `b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836`)
  - `ai_img/ai_image_detection/models/fc_weights.pth` (4 KB, SHA-256: `477100745713bcc957beb2b40859536859b6483fd6301b3b9293151b194c7847`)
- **Endpoints**:
  - `GET /api/ai_image_detection/health` -> `{"status": "ok", "module": "ai_image_detection"}`
  - `POST /api/ai_image_detection/analyze`:
    - Method: `POST`
    - Form Field: `file` (`UploadFile`, multipart/form-data)
  - `GET /api/ai_image_detection/artifacts/{filename}` -> PNG crop-score heatmap
- **Key Forensic Rule**:
  - Calibrated probability: `raw_metrics.calibrated_probability` (P(fake) from 0.0 to 1.0).
  - Verdicts: `authentic` ("Real"), `likely_tampered` ("Likely fake"), `inconclusive` ("Uncertain"), or Quality Gate Flag ("Insufficient quality" for small/blurry images).
  - Exposes 9 crop score breakdown and EXIF/metadata photo classification.
- **Verified Benchmark Run Time**: ~13 seconds cold / ~2-3 seconds warm on CPU.

---

## 3. `image_forgery` (TruFor Tamper Localization)

- **Purpose**: Image Tamper Detection, Splicing & Copy-Move Localization. Deep RGB+noise transformer (TruFor) combined with Error Level Analysis (ELA) and forensic metadata analysis.
- **Root Directory**: `image_forgery/image_forgery` (sub-package inside `image_forgery`)
- **Default Port**: `8003` (internal)
- **Python Version**: `3.13` (compatible with 3.10+)
- **Entry Point**: `main_standalone:app` (FastAPI)
- **Model Files**:
  - `image_forgery/image_forgery/models/trufor/trufor.pth.tar` (281 MB, SHA-256: `ac1d90e329a72e0d66e8665e123a19e94bfae3209c3ef8a4f9ca3b91578c7844`)
- **Endpoints**:
  - `GET /api/image_forgery/health` -> `{"status": "ok", "module": "image_forgery"}`
  - `GET /api/image_forgery/engines` -> List of forensic engines (TruFor, ELA, Metadata)
  - `POST /api/image_forgery/analyze`:
    - Method: `POST`
    - Form Field: `file` (`UploadFile`, multipart/form-data)
    - Optional Field: `options` (`str` containing JSON)
  - `GET /api/image_forgery/artifacts/{filename}` -> Generated heatmap overlay and ELA images
- **Key Forensic Rule**:
  - Outputs image-level integrity score (`raw_metrics.engines.trufor.global_score`) from TruFor.
  - Generates pixel-level anomaly heatmap overlay (`trufor_overlay.png`) and ELA artifact (`ela.png`).
  - Output displays each model/engine separately; scores are never averaged across different engines.
- **Verified Benchmark Run Time**: ~14 seconds cold / ~3-4 seconds warm on CPU.

---

## 4. `ai_cctv` (AI CCTV Tampering & Synthesis Detection)

- **Purpose**: CCTV Video AI-Synthesis & Tampering Detection using temporal windowing, native 224x224 tile analysis, fine-tuned YOLO11s classifier, and Platt probability scaling.
- **Root Directory**: `ai_cctv`
- **Default Port**: `8004` (internal)
- **Python Version**: `3.10`
- **Entry Point**: `main_standalone:app` (FastAPI)
- **Model Files**:
  - `ai_cctv/ai_cctv_detection/models/best.pt` (11 MB, SHA-256: `4dc60327c256cb9576b56ad142184c7597485d8d0511352d4e8a518744fbcc30`)
  - `ai_cctv/models/yolo11s-cls.pt` (13.6 MB, SHA-256: `e2b605d1c8c212b434a75a32759a6f7adf1d2b29c35f76bdccd4c794cb653cf2`)
- **Endpoints**:
  - `GET /api/ai_cctv_detection/health` -> `{"status": "ok", "module": "ai_cctv_detection"}`
  - `POST /api/ai_cctv_detection/analyze`:
    - Method: `POST`
    - Form Field: `file` (`UploadFile`, multipart/form-data)
    - Query Parameters: `job_id` (optional), `tracking` (`bool`)
  - `GET /api/ai_cctv_detection/progress/{job_id}` -> `{"job_id": str, "stage": str, "percent": int}`
  - `GET /api/ai_cctv_detection/artifacts/{filename}` -> Timeline PNG chart
- **Key Forensic Rule**:
  - Aggregates per-frame AI probabilities (`frame_scores` array with timestamp and score).
  - Video analysis runs as an async background job with progress reporting.
  - Verdicts: `authentic` ("Likely real"), `likely_tampered` ("Likely AI-generated"), `inconclusive` ("Inconclusive - send for human review").
- **Verified Benchmark Run Time**: ~3.5 seconds on test clip with 3 sampled frames.
