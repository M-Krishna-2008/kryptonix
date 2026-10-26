# Size Report: PS-05 AI CCTV Detection Module

**Target Module**: `ai_cctv_detection`  
**Measurement Date**: October 25, 2026  
**Initial Total Size**: ~10.07 GB (10,819,957,842 bytes)  

---

## 1. Top-Level Directory and Component Breakdown

| Directory / Item | Size (Bytes) | Size (MB) | Size (GB) | File Count | Classification | Description |
|---|---|---|---|---|---|---|
| `.venv/` | 5,574,885,825 | 5,316.63 MB | 5.19 GB | 32,292 | **Tier C** | Python virtual environment with PyTorch CUDA wheels, OpenCV, dependencies. Regenerable via `run_platform.bat`. |
| `_backup/` | 2,621,071,371 | 2,499.65 MB | 2.44 GB | 2 | **Archive** | Safety backups created before codebase modifications (`yolo_project_backup.zip` and `safety_backup_code_configs_models.zip`). |
| `data/` | 1,130,454,725 | 1,078.09 MB | 1.05 GB | 2,159 | **Tier B** | Extracted video frame images for training/val/test splits (`train/`, `val/`, `test/`). Needed only to retrain model. |
| `data_raw/` | 641,545,799 | 611.83 MB | 0.60 GB | 20 | **Tier B** | Original CCTV evidence source clips (10 authentic, 10 tampered). Needed only for dataset regeneration. |
| `real/` | 551,227,682 | 525.69 MB | 0.51 GB | 10 | **Tier B** | Redundant user drop folder (identical bit-for-bit to `data_raw/real/`). Archive with Tier B. |
| `uploads/` | 139,471,877 | 133.01 MB | 0.13 GB | 6 | **Tier C** | Temporary upload directory for incoming multipart/form-data video evidence. Created automatically at runtime. |
| `tamp/` | 90,318,117 | 86.13 MB | 0.08 GB | 10 | **Tier B** | Redundant user drop folder (identical bit-for-bit to `data_raw/fake/`). Archive with Tier B. |
| `runs/` | 29,878,746 | 28.49 MB | 0.03 GB | 27 | **Tier B** | YOLO11 training checkpoints, training metrics, confusion matrices, and `last.pt` (needed to resume training). |
| `models/` | 24,654,491 | 23.51 MB | 0.02 GB | 2 | **Tier D** | Root weights directory containing base checkpoint `yolo11s-cls.pt` (13.6 MB) and copy of `best.pt` (11.0 MB). |
| `ai_cctv_detection/` | 11,168,310 | 10.65 MB | 0.01 GB | 19 | **Tier D** | Core forensic module package: `analyzer.py`, `router.py`, `schemas.py`, `static/`, `configs/`, and active detector `models/best.pt`. |
| `artifacts/` | 6,893,021 | 6.57 MB | 0.01 GB | 13 | **Tier C** | Generated visual forensic artifacts (score timelines, contact sheets, heatmaps). Re-created on-demand per analysis. |
| `weights/` | 5,544,453 | 5.29 MB | 0.01 GB | 1 | **Tier A** | Auto-downloaded Ultralytics AMP benchmark weight (`yolo26n.pt`). Regenerable junk. |
| `tests/` | 1,797,232 | 1.71 MB | 0.00 GB | 6 | **Tier D** | Test suite fixtures, synthetic video generator, unit tests, and validation clip `api_test_clip.mp4`. |
| `cache/` | 68,426 | 0.07 MB | 0.00 GB | 3 | **Tier C** | SHA-256 analysis report caches for fast re-evaluations. Auto-regenerated at runtime. |
| `tools/` | 44,714 | 0.04 MB | 0.00 GB | 8 | **Tier D** | Retraining utilities: `build_dataset.py`, `train.py`, `calibrate.py`, `metadata_check.py`. |
| `__pycache__/` | 3,538 | 0.00 MB | 0.00 GB | 1 | **Tier A** | Bytecode cache for root scripts. Regenerable. |
| `.pytest_cache/` | 1,259 | 0.00 MB | 0.00 GB | 4 | **Tier A** | Pytest runtime cache. Regenerable. |
| `scripts/` | 893 | 0.00 MB | 0.00 GB | 1 | **Tier D** | Launcher helper script `scripts/launcher_helper.ps1` for disk checks and dynamic port allocation. |
| `logs/` | 509 | 0.00 MB | 0.00 GB | 5 | **Tier C** | Setup and launcher diagnostic execution logs. |
| Root Docs & Batch Scripts | ~70,000 | 0.07 MB | 0.00 GB | 18 | **Tier D** | `run_platform.bat`, `stop_platform.bat`, `check_system.bat`, `requirements-lock.txt`, `MODULE_MANIFEST.json`, `ENVIRONMENT.md`, etc. |

---

## 2. Top 20 Largest Files

| # | File Path | Size (Bytes) | Size (MB) | Tier | Description |
|---|---|---|---|---|---|
| **1** | `_backup/yolo_project_backup.zip` | 2,581,478,253 | 2,461.89 MB | **Archive** | Full zip backup of original working project before changes. |
| **2** | `.venv/Lib/site-packages/torch/lib/torch_cuda.dll` | 957,267,456 | 912.92 MB | **Tier C** | PyTorch CUDA runtime DLL inside virtual environment. |
| **3** | `.venv/Lib/site-packages/torch/lib/dnnl.lib` | 653,534,016 | 623.26 MB | **Tier C** | Deep Neural Network Library static binary. |
| **4** | `.venv/Lib/site-packages/torch/lib/cudnn_engines_precompiled64_9.dll` | 588,910,632 | 561.63 MB | **Tier C** | cuDNN precompiled CUDA neural net engines. |
| **5** | `.venv/Lib/site-packages/torch/lib/cublasLt64_12.dll` | 472,802,816 | 450.90 MB | **Tier C** | NVIDIA cuBLAS linear algebra runtime library. |
| **6** | `.venv/Lib/site-packages/torch/lib/cufft64_11.dll` | 291,784,192 | 278.27 MB | **Tier C** | Fast Fourier Transform CUDA library. |
| **7** | `.venv/Lib/site-packages/torch/lib/cusparse64_12.dll` | 275,632,128 | 262.86 MB | **Tier C** | Sparse matrix CUDA operations library. |
| **8** | `.venv/Lib/site-packages/torch/lib/torch_cpu.dll` | 251,258,368 | 239.62 MB | **Tier C** | PyTorch CPU fallback execution engine. |
| **9** | `.venv/Lib/site-packages/torch/lib/cudnn_adv64_9.dll` | 241,576,488 | 230.39 MB | **Tier C** | cuDNN advanced neural network layer routines. |
| **10** | `.venv/Lib/site-packages/_polars_runtime_32/_polars_runtime.pyd` | 171,975,680 | 164.01 MB | **Tier C** | Polars Rust runtime extension inside `.venv`. |
| **11** | `.venv/Lib/site-packages/torch/lib/cusolver64_11.dll` | 114,861,056 | 109.54 MB | **Tier C** | LAPACK/Solver CUDA library. |
| **12** | `.venv/Lib/site-packages/torch/lib/cudnn_ops64_9.dll` | 107,721,256 | 102.73 MB | **Tier C** | cuDNN operator routines. |
| **13** | `.venv/Lib/site-packages/torch/lib/cublas64_12.dll` | 100,188,672 | 95.55 MB | **Tier C** | cuBLAS matrix multiplication library. |
| **14** | `.venv/Lib/site-packages/torch/lib/cudnn_heuristic64_9.dll` | 85,741,608 | 81.77 MB | **Tier C** | cuDNN heuristic decision engine. |
| **15** | `.venv/Lib/site-packages/torch/lib/cusolverMg64_11.dll` | 78,133,248 | 74.51 MB | **Tier C** | cuSolver multi-GPU support library. |
| **16** | `.venv/Lib/site-packages/cv2/cv2.pyd` | 74,938,880 | 71.47 MB | **Tier C** | OpenCV Python C-extension binding. |
| **17** | `.venv/Lib/site-packages/torch/lib/curand64_10.dll` | 63,308,800 | 60.38 MB | **Tier C** | CUDA pseudorandom number generator library. |
| **18** | `data_raw/real/1.mp4` | 61,970,117 | 59.10 MB | **Tier B** | Authentic CCTV source training video. |
| **19** | `real/1.mp4` | 61,970,117 | 59.10 MB | **Tier B** | Redundant identical copy of `data_raw/real/1.mp4`. |
| **20** | `data_raw/real/9.mp4` | 61,858,973 | 58.99 MB | **Tier B** | Authentic CCTV source training video. |

---

## 3. Git Repository Status
- **`.git` Folder Presence**: None. The project was distributed/worked on as a clean local workspace with no active `.git/` history directory.

---

## 4. Model File Inventory & Deduplication Analysis

| Model Path | Size | SHA-256 Checksum | Active Role |
|---|---|---|---|
| `ai_cctv_detection/models/best.pt` | 11,024,379 bytes | `4dc60327c256cb9576b56ad142184c7597485d8d0511352d4e8a518744fbcc30` | **Primary Detector**: Loaded directly by `ai_cctv_detection/analyzer.py` via `BEST_MODEL_PATH = MODELS_DIR / "best.pt"`. |
| `models/best.pt` | 11,024,379 bytes | `4dc60327c256cb9576b56ad142184c7597485d8d0511352d4e8a518744fbcc30` | **Root Mirror**: Checked as fallback by `run_platform.bat`. Exact binary duplicate of `ai_cctv_detection/models/best.pt`. |
| `runs/.../weights/best.pt` | 11,024,379 bytes | `4dc60327c256cb9576b56ad142184c7597485d8d0511352d4e8a518744fbcc30` | **Training Artifact**: Saved by Ultralytics during training epoch completion. Exact duplicate of `best.pt`. |
| `runs/.../weights/last.pt` | 11,024,379 bytes | `1d91b791e1c0ffcccd73b002dd9168bdad165ecd3ff32dca7034ac54c1ae8707` | **Training Checkpoint**: Needed only if resuming training from epoch 15. |
| `models/yolo11s-cls.pt` | 13,630,112 bytes | `e2b605d1c8c212b434a75a32759a6f7adf1d2b29c35f76bdccd4c794cb653cf2` | **Base Architecture Weights**: Stock Ultralytics checkpoint. Auto-downloadable from GitHub releases. |
| `weights/yolo26n.pt` | 5,544,453 bytes | `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` | **Ultralytics Benchmark Cache**: Safe to delete (Tier A). |

---

## 5. Runtime Coupling Audit (Tier B & Tier C Verification)
- **Tier B Dependency Check**: Verified that `analyzer.py`, `router.py`, `schemas.py`, and `main_standalone.py` have **zero read dependencies** on `data/`, `data_raw/`, or `runs/`. These folders are strictly consumed by `tools/` during training or dataset building.
- **Tier C Dependency Check**: `uploads/`, `artifacts/`, and `cache/` are used strictly for **runtime read/write caching and file staging**. The application ensures their creation dynamically via `os.makedirs(..., exist_ok=True)`. They contain no static runtime code or bundled models and are safe to exclude from the transfer package.

---

## 6. Size Reduction & Package Summary (Before vs. After)

| Package / State | Size (Bytes) | Size (MB / GB) | Description |
|---|---|---|---|
| **Original Workspace (Before)** | 10,819,957,842 bytes | **~10.07 GB** | Complete uncleaned workspace including `.venv`, extracted frames, raw clips, backups, and caches. |
| **Current Project Workspace (On Disk)** | 78,561,000 bytes | **74.92 MB** | **99.31% total disk space reduction**. Contains all code, models, tests, configs, tools, plus the generated runtime zip (`dist/`). Uncompressed project files alone are only **38.91 MB**. |
| **Slim Runtime Transfer Package (`dist/ai_cctv_detection_runtime_20261025.zip`)** | 37,760,711 bytes | **36.01 MB** | **Submission artifact**. Contains everything needed for judges/evaluators to run the complete platform. |
| **Separated Backup Folder (`Downloads/backup/`)** | 5,064,496,440 bytes | **4.72 GB** | Safe external storage of `_backup/` (2.44 GB) and `_archive_training_data/` (2.28 GB) outside the project root. |


