# CCTV Evidence AI Model Training Protocol

This guide outlines the protocol for fine-tuning YOLO11-cls to produce `ai_cctv_detection/models/best.pt`.

## 1. Principles of Forensic Honesty
- **Stock Pretrained Weights Cannot Detect AI**: A stock YOLO classifier knows generic objects (cats, cars), not diffusion artifacts or synthetic temporal jitter. Never use random weights or pretrained weights without domain fine-tuning.
- **Never Fake Evidence**: If `best.pt` is missing, the module returns an `inconclusive` verdict with an informative notice.

---

## 2. Dataset Collection Rules

### Matched Camera & Codec Distributions
AI video generators often output pristine 1080p MP4s with high bitrates, while CCTV streams use low bitrates, sensor noise, wide-angle lens distortion, and compression blockiness.
- **Resolution Matching**: Ensure real and synthetic videos share standard CCTV resolutions (e.g., 720p, 1080p).
- **Codec & Bitrate**: Re-encode AI videos using typical CCTV settings (H.264, 1.5–4 Mbps, variable frame rates).
- **Timecode & Overlays**: If real CCTV contains on-screen display (OSD) timecodes, overlay similar timestamps on AI videos so the network does not treat OSD text as a discriminator.

### Generator Diversity
Include clips from multiple generative video architectures:
- Sora
- Runway Gen-2 / Gen-3
- Luma Dream Machine
- Kling AI
- Open-source video diffusion (CogVideoX, Stable Video Diffusion, AnimateDiff)

### Held-Out Evaluation Protocol
- **Hold out at least one entire generator family** (e.g., train on Runway + Luma, evaluate on Kling) to test out-of-distribution generalization.
- **Split Strictly By Source Video**: `tools/build_dataset.py` enforces splitting by source video rather than by frame, preventing identical backgrounds from appearing in both train and validation splits.

---

## 3. Training & Calibration Steps

### Step 1: Prepare Raw Video Directories
Place CCTV footage in:
```
data_raw/
  real/       # Authentic CCTV camera recordings (.mp4, .avi, .mkv)
  fake/       # AI-generated CCTV simulations (.mp4, .avi, .mkv)
```

### Step 2: Run Automated Training Launcher
Execute the automated batch runner:
```bat
train_model.bat
```
Or execute each step manually:

```bash
# 1. Extract frames and split by video ID
python tools/build_dataset.py data_raw/real data_raw/fake --output-dir data

# 2. Check for shortcut learning
python tools/metadata_check.py --manifest data/manifest.json

# 3. Fine-tune YOLO11-cls
python tools/train.py --data-dir data --epochs 25

# 4. Fit Platt scaling calibration on held-out validation set
python tools/calibrate.py --model ai_cctv_detection/models/best.pt --val-dir data/val
```

### Step 3: Verify Model Checkpoint
Ensure `ai_cctv_detection/models/best.pt` exists and restart the platform:
```bat
run_platform.bat
```
The UI banner will automatically switch to active detection mode.
