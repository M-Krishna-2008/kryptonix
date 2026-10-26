# Archived Training Data Inventory: PS-05 AI CCTV Detection

**Archive Status**: FULLY COPIED & VERIFIED (Originals preserved in project pending user approval)  
**Archive Location**: `C:\Users\Grish ragav\Downloads\yolo project\_archive_training_data`  
**Archive Manifest**: `_archive_training_data\ARCHIVE_MANIFEST.txt`  
**Creation Date**: October 25, 2026  
**Total Archived Size**: 2,443,425,069 bytes (2.28 GB) across 2,226 files  

---

## 1. Archived Components

| Component | Source Path | Files | Total Bytes | Purpose |
|---|---|---|---|---|
| **Extracted Frames** | `data/` | 2,159 | 1,130,454,725 | Native video frame extracts organized into `train/`, `val/`, `test/` splits. |
| **Raw Evidence Clips** | `data_raw/` | 20 | 641,545,799 | 10 authentic CCTV videos and 10 tampered/AI-generated CCTV videos. |
| **User Drop Folders** | `real/`, `tamp/` | 20 | 641,545,799 | Source files provided in root drop folders (exact duplicates of `data_raw/`). |
| **Training Run Artifacts** | `runs/` | 27 | 29,878,746 | YOLO11 training checkpoints, confusion matrices, and `last.pt` (epoch 15). |

---

## 2. Integrity Verification Details
- **File Count Verification**: 100% matched across all subdirectories.
- **Byte Count Verification**: 100% bit-exact byte total match (`2,443,425,069` bytes).
- **Random Sample SHA-256 Check**: 50 random files across training frames, raw MP4s, and YOLO checkpoints were hashed. 50 of 50 matched their source files with zero errors.

---

## 3. How to Restore Training Data

To restore the training data back into the project repository at any time:

```cmd
restore_training_data.bat "_archive_training_data"
```

Or from any external backup path:
```cmd
restore_training_data.bat "D:\Forensics_Archive\PS05_Training_Data"
```

The script will copy all folders (`data\`, `data_raw\`, `runs\`, `real\`, `tamp\`) back into the project root and perform bit-level verification before concluding.

---

## 4. Retraining Behavior When Data is Archived
All training tools (`tools/build_dataset.py`, `tools/train.py`, `tools/calibrate.py`, `tools/metadata_check.py`) have been updated with clean guard clauses. If executed while data is archived, they gracefully inform the forensic operator:
```text
[ERROR] Training data directory missing.
Training data is archived. Run restore_training_data.bat <archive folder>
```
The active detector `ai_cctv_detection/models/best.pt` remains 100% active and functional for runtime inference regardless of whether training data is archived.
