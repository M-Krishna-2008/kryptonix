# PS-05 Platform Deep Clean & Repo-Ready Packaging Report

**Project Root:** `c:\Users\galah\Downloads\bihar`  
**External Backup Path:** `c:\Users\galah\Downloads\PS05_backup_20261026`  
**Date:** 26 October 2026  
**Status:** Clean, packaged, validated with fresh clone smoke test.

---

## 1. Executive Summary: Before vs. After Metrics

| Metric | Before Cleanup | After Cleanup (Repo Ready) | Reduction |
| :--- | :--- | :--- | :--- |
| **Total Directory Size** | **16,331.65 MB** (15.95 GB) | **17.94 MB** (Working Tree) | **99.89%** |
| **Total File Count** | **142,719 files** | **254 files** | **99.82%** |
| **Tracked Git Size** | N/A (Not initialized) | **17.94 MB** (Under 20 MB target) | Optimized |
| **Git Database (`.git`)** | 0 MB | **16.11 MB** | Ultra-compact |
| **External Backup Size** | 0 MB | **16,255.73 MB** (15.87 GB) | 100% Preserved |
| **Largest Tracked File** | 3,632.42 MB (`xlsr2_300m.pt`) | **10.51 MB** (`best.pt`, trained) | < 25 MB limit |

---

## 2. Step 1: Pre-Clean Measurement Breakdown

### A. Top 40 Largest Files (Before Clean)
1. `ai_aud\audio_forensics\models\xlsr2_300m.pt`: 3,632.42 MB (Model weight)
2. `ai_aud\audio_forensics\models\LA_model.pth`: 1,212.72 MB (Model weight)
3. `ai_img\.venv\Lib\site-packages\torch\lib\torch_cuda.dll`: 912.92 MB (Virtualenv DLL)
4. `ai_img\ai_image_detection\models\clip\ViT-L-14.pt`: 889.56 MB (Model weight)
5. `ai_img\ai_image_detection\models\ViT-L-14.pt`: 889.56 MB (Unreferenced duplicate)
6. `ai_img\.venv\Lib\site-packages\torch\lib\dnnl.lib`: 623.26 MB (Virtualenv static lib)
7. `ai_img\.venv\Lib\site-packages\torch\lib\cudnn_engines_precompiled64_9.dll`: 561.63 MB (Virtualenv DLL)
8. `ai_img\.venv\Lib\site-packages\torch\lib\cublasLt64_12.dll`: 450.90 MB (Virtualenv DLL)
9. `ai_aud\.venv\Lib\site-packages\torch\lib\torch_cpu.dll`: 291.72 MB (Virtualenv DLL)
10. `ai_aud\test_venv\Lib\site-packages\torch\lib\torch_cpu.dll`: 291.72 MB (Virtualenv DLL)
11. `ai_cctv\.venv\Lib\site-packages\torch\lib\torch_cpu.dll`: 291.72 MB (Virtualenv DLL)
12. `ai_img\.venv\Lib\site-packages\torch\lib\cufft64_11.dll`: 278.27 MB (Virtualenv DLL)
13. `image_forgery\image_forgery\models\trufor\trufor.pth.tar`: 268.46 MB (Model weight)
14. `ai_img\.venv\Lib\site-packages\torch\lib\cusparse64_12.dll`: 262.86 MB (Virtualenv DLL)
15. `ai_img\.venv\Lib\site-packages\torch\lib\torch_cpu.dll`: 239.62 MB (Virtualenv DLL)
16. `ai_img\.venv\Lib\site-packages\torch\lib\cudnn_adv64_9.dll`: 230.39 MB (Virtualenv DLL)
17. `ai_cctv\.venv\Lib\site-packages\_polars_runtime_32\_polars_runtime.pyd`: 164.01 MB (Virtualenv DLL)
18. `image_forgery\image_forgery\third_party\TruFor\.git\objects\pack\pack-ae16b5...pack`: 128.18 MB (Embedded Git)
19. `ai_aud\.venv\Lib\site-packages\llvmlite\binding\llvmlite.dll`: 114.79 MB (Virtualenv DLL)
20. `ai_aud\test_venv\Lib\site-packages\llvmlite\binding\llvmlite.dll`: 114.79 MB (Virtualenv DLL)
21. `ai_img\.venv\Lib\site-packages\torch\lib\cusolver64_11.dll`: 109.54 MB (Virtualenv DLL)
22. `ai_img\.venv\Lib\site-packages\torch\lib\cudnn_ops64_9.dll`: 102.73 MB (Virtualenv DLL)
23. `ai_img\.venv\Lib\site-packages\torch\lib\cublas64_12.dll`: 95.55 MB (Virtualenv DLL)
24. `image_forgery\image_forgery\third_party\TruFor\TruFor_train_test\pretrained_models\segformers\mit_b2.pth`: 94.31 MB (Model weight)
25. `ai_img\.venv\Lib\site-packages\cv2\cv2.pyd`: 82.30 MB (Virtualenv DLL)
26. `ai_img\.venv\Lib\site-packages\torch\lib\cudnn_heuristic64_9.dll`: 81.77 MB (Virtualenv DLL)
27. `ai_img\.venv\Lib\site-packages\torch\lib\cusolverMg64_11.dll`: 74.51 MB (Virtualenv DLL)
28. `ai_cctv\.venv\Lib\site-packages\cv2\cv2.pyd`: 71.47 MB (Virtualenv DLL)
29. `ai_img\.venv\Lib\site-packages\torch\lib\curand64_10.dll`: 60.38 MB (Virtualenv DLL)
30. `ai_img\.venv\Lib\site-packages\torch\lib\nvrtc64_120_0.dll`: 42.66 MB (Virtualenv DLL)
31. `ai_img\.venv\Lib\site-packages\torch\lib\libprotoc.lib`: 37.80 MB (Virtualenv static lib)
32. `ai_cctv\uploads\8349dee9-4757-4f8e-9516-e5e1a8a0e001_download.mp4`: 37.51 MB (User test upload)
33. `ai_img\.venv\Lib\site-packages\torch\lib\nvJitLink_120_0.dll`: 36.47 MB (Virtualenv DLL)
34. `ai_aud\test_venv\Lib\site-packages\numpy.libs\libopenblas...dll`: 36.40 MB (Virtualenv DLL)
35. `ai_aud\.venv\Lib\site-packages\numpy.libs\libopenblas...dll`: 36.40 MB (Virtualenv DLL)
36. `ai_cctv\.venv\Lib\site-packages\numpy.libs\libopenblas...dll`: 36.40 MB (Virtualenv DLL)
37. `ai_img\.venv\Lib\site-packages\torch\lib\libprotobuf.lib`: 36.04 MB (Virtualenv static lib)
38. `ai_img\.venv\Lib\site-packages\cv2\opencv_videoio_ffmpeg500_64.dll`: 29.45 MB (Virtualenv DLL)
39. `image_forgery\image_forgery\third_party\TruFor\TruFor_train_test\dataset\data\bcmc_COCO_train_list.txt`: 28.46 MB (Dataset metadata)
40. `ai_cctv\.venv\Lib\site-packages\torch\lib\torch_cpu.lib`: 27.97 MB (Virtualenv static lib)

### B. Top 20 Largest Directories (Before Clean)
1. `ai_aud`: 7,275.45 MB
2. `ai_img`: 6,807.99 MB
3. `ai_img\.venv`: 4,973.94 MB
4. `ai_img\.venv\Lib\site-packages`: 4,971.27 MB
5. `ai_img\.venv\Lib`: 4,971.27 MB
6. `ai_aud\audio_forensics`: 4,846.13 MB
7. `ai_aud\audio_forensics\models`: 4,845.14 MB
8. `ai_img\.venv\Lib\site-packages\torch`: 4,464.47 MB
9. `ai_img\.venv\Lib\site-packages\torch\lib`: 4,358.54 MB
10. `ai_img\ai_image_detection`: 1,780.21 MB
11. `ai_img\ai_image_detection\models`: 1,779.12 MB
12. `ai_cctv`: 1,452.46 MB
13. `ai_cctv\.venv`: 1,246.60 MB
14. `ai_cctv\.venv\Lib\site-packages`: 1,243.58 MB
15. `ai_cctv\.venv\Lib`: 1,243.58 MB
16. `ai_aud\.venv`: 1,170.69 MB
17. `ai_aud\test_venv`: 1,167.68 MB
18. `ai_aud\.venv\Lib`: 1,165.44 MB
19. `ai_aud\.venv\Lib\site-packages`: 1,165.44 MB
20. `ai_aud\test_venv\Lib`: 1,162.53 MB

---

## 3. Disposition Table (Actions Taken)

| Category / Item | Original Size | Action Taken | Rationale & Handling |
| :--- | :--- | :--- | :--- |
| **All Virtual Environments** (`.venv`, `test_venv`) | 8,618.14 MB | **Moved to Backup** | 140,041 files. Consolidated into single root `.venv` provisioned automatically by `run.bat`. |
| **Large Models > 25 MB** (`xlsr2`, `LA_model`, `ViT-L-14`, `trufor`, `mit_b2`) | 6,892.71 MB | **Moved to Backup / Auto-download** | Public research models. Documented in `models/MODELS.json` and auto-downloaded by launcher with resume & hash check. |
| **Embedded Git Repo** (`third_party/TruFor/.git`) | 128.24 MB | **Moved to Backup** | Embedded repository would break root git tracking and added 128 MB bloat. |
| **TruFor Training Artifacts** (`TruFor_train_test`, `docs`) | 199.84 MB | **Moved to Backup** | Unused for inference. `test_docker/src/` provides the actual runtime inference engine. |
| **Duplicate Models** (`ViT-L-14.pt`, `best.pt`) | 900.07 MB | **Moved to Backup** | Redundant copies removed; canonical paths maintained in module directories. |
| **Personal / Test Media** (`WhatsApp Audio`, `data_audio`, `uploads`, `artifacts`) | 410.15 MB | **Moved to Backup** | Privacy and license risk. Replaced with tiny synthetic test fixtures (<5 MB). |
| **Bundled Offline Wheels** (`fairseq`, `numpy`) | 24.94 MB | **Moved to Backup / Auto-download** | NumPy installs via PyPI; Fairseq installs from automated GitHub release wheel. |
| **Runtime Logs & Result Caches** (`logs/`, `cache/`) | 11.53 MB | **Moved to Backup** | Transient runtime outputs; recreated upon launch. |
| **Transient Bytecode & Cache** (`__pycache__`, `*.pyc`, `.pytest_cache`) | 0.50 MB | **Deleted (Safe)** | Ephemeral Python artifacts recreated automatically. |
| **Trained Weight Under 25 MB** (`ai_cctv_detection/models/best.pt`) | 10.51 MB | **COMMITTED** | Fine-tuned project artifact explicitly permitted under 25 MB limit. |
| **Trained Weight Under 25 MB** (`ai_image_detection/models/fc_weights.pth`) | 0.004 MB | **COMMITTED** | Linear probe classifier weights (<25 MB). |
| **Source Code, UI, Configs, Tests, Docs** | ~7.43 MB | **COMMITTED** | Clean repository core (254 files total). |

---

## 4. Models Manifest & Downloader (`models/MODELS.json`)

All large models are defined in `models/MODELS.json`:

1. **`xlsr2_300m.pt`** (3.63 GB)
   - Destination: `ai_aud/audio_forensics/models/xlsr2_300m.pt`
   - SHA-256: `b08927597f2c9eb2ebd7dcc3ac78ee4b5f6021cbac4b3a6c5a9deec445d80ed9`
   - URL: `https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt`
   - License: CC-BY-NC 4.0
2. **`LA_model.pth`** (1.21 GB)
   - Destination: `ai_aud/audio_forensics/models/LA_model.pth`
   - SHA-256: `bd6f36097259fe54e7004eb983651e5304d807be81156dbd04faccb70d91e10c`
   - URL: `https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST/resolve/main/LA_model.pth`
   - License: ASVspoof Research / MIT
3. **`ViT-L-14.pt`** (889.56 MB)
   - Destination: `ai_img/ai_image_detection/models/clip/ViT-L-14.pt`
   - SHA-256: `b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836`
   - URL: `https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt`
   - License: MIT
4. **`trufor.pth.tar`** (268.46 MB)
   - Destination: `image_forgery/image_forgery/models/trufor/trufor.pth.tar`
   - SHA-256: `ac1d90e329a72e0d66e8665e123a19e94bfae3209c3ef8a4f9ca3b91578c7844`
   - URL: `https://huggingface.co/spaces/FraudDetection/trufor-splicing-detecto/resolve/main/TruFor_train_test/pretrained_models/trufor.pth.tar`
   - License: Nonprofit / Forensic evaluation (GRIP Unina)
5. **`yolo11s-cls.pt`** (13.00 MB)
   - Destination: `ai_cctv/models/yolo11s-cls.pt`
   - SHA-256: `e2b605d1c8c212b434a75a32759a6f7adf1d2b29c35f76bdccd4c794cb653cf2`
   - URL: `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s-cls.pt`
   - License: AGPL-3.0

The root launcher `run.bat` automatically parses this manifest, verifies existing hashes (never redownloading good files), resumes interrupted downloads via `curl -C -`, and gracefully handles network failure by printing manual instructions while still starting the UI.

---

## 5. Verification: Fresh Clone Test (`C:\Temp\ps05 clone test`)

A complete simulation of a fresh clone on another PC was executed in a folder with spaces (`C:\Temp\ps05 clone test`):
1. **Clone Metrics (before setup):**
   - Total Clone Size: **34.08 MB**
   - Working Tree Size: **17.97 MB**
   - Git Database (`.git`): **16.11 MB**
2. **Dry Run Execution (`run.bat /dryrun`):**
   - Python 3.10 detected.
   - All 7 model entries verified or mapped to download URLs.
   - Ports 8080, 8001, 8002, 8003, 8004 allocated dynamically.
   - Pre-flight checks passed cleanly with code 0.
3. **Live Startup (`run.bat -NoBrowser`):**
   - Root virtual environment provisioned and pinned to `numpy==1.26.4`.
   - All 4 module services and the Gateway started.
   - Health checks turned green within 4 seconds.
4. **End-to-End Smoke Test (`scripts/smoke_test.ps1`):**
   - `Gateway /api/health Aggregator`: **[PASS]**
   - `Gateway /api/config Manifest Delivery`: **[PASS]**
   - `Module [ai_aud] Audio Forensics Analysis`: **[PASS]**
   - `Module [ai_img] AI Image Synthesis Detection`: **[PASS]**
   - `Module [image_forgery] TruFor Tamper Localization`: **[PASS]**
   - `Module [ai_cctv] Video Timeline & Quality Gate`: **[PASS]**
   - `Gateway Content Signature Validation`: **[PASS]**
   - **Result: 7 / 7 tests passed.**
5. **Clean Shutdown (`stop.bat`):**
   - All background PIDs terminated and ports freed.
6. **Second Launch & Double-Click Verification:**
   - Fixed argument forwarding in `run.bat` to eliminate unwanted dry-run flag triggering when launched with no arguments (e.g. from Explorer double-click).
   - Skipped virtualenv creation, skipped model re-downloading, and started in seconds.

---

## 6. Action Items for the User

No manual model uploads to GitHub Releases are required because all 5 large models have stable upstream canonical direct download links in `models/MODELS.json`. 

The only items in the external backup folder `c:\Users\galah\Downloads\PS05_backup_20261026` are:
1. Your personal audio clip (`WhatsApp Audio 2026-10-24 at 14.08.51.mp3`)
2. Historical benchmark datasets (`data_audio/`, `data_diagnosis/`)
3. Past analysis run caches and old duplicate virtual environments
