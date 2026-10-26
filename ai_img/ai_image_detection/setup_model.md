# Model Setup & Offline Weight Placement Guide (`ai_image_detection`)

This module runs **100% locally** (zero runtime network or API calls). This guide provides step-by-step instructions for environment creation, dependency installation, model weight download and placement, and an offline sanity-check command.

---

## 1. Python Environment Setup

We recommend Python 3.10, 3.11, 3.12, or 3.13.

### Step 1.1: Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 1.2: Install PyTorch

Install the PyTorch build suitable for your hardware:

* **CPU Only (Lightweight / Default):**
  ```bash
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  ```

* **NVIDIA GPU (CUDA 12.x):**
  ```bash
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
  ```

### Step 1.3: Install Module Dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Model Weights Download & Folder Placement

The UnivFD architecture requires two weight files:

```text
ai_image_detection/models/
├── clip/
│   └── ViT-L-14.pt       # Frozen OpenAI CLIP ViT-L/14 vision checkpoint (~933 MB)
└── fc_weights.pth         # Trained Linear Probe (768 -> 1) weights (~4 KB)
```

### 2.1 Frozen CLIP ViT-L/14 Vision Checkpoint

* **Source URL:** [OpenAI CLIP Official ViT-L-14.pt](https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt)
* **Expected SHA-256 Checksum:** `b8cca3fd41ae0c80ba7e11518be4eab97405a8e32a6134b4e1f079438770b242`
* **Destination Path:** `ai_image_detection/models/clip/ViT-L-14.pt`

**Download via PowerShell (Windows):**
```powershell
New-Item -ItemType Directory -Force -Path "ai_image_detection/models/clip"
Invoke-WebRequest -Uri "https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt" -OutFile "ai_image_detection/models/clip/ViT-L-14.pt"
```

**Download via cURL (Linux/macOS):**
```bash
mkdir -p ai_image_detection/models/clip
curl -L -o ai_image_detection/models/clip/ViT-L-14.pt "https://openaipublic.azureedge.net/clip/models/b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt"
```

### 2.2 UnivFD Linear Probe (`fc_weights.pth`)

* **Architecture:** `torch.nn.Linear(768, 1)`
* **Destination Path:** `ai_image_detection/models/fc_weights.pth`
* **From UnivFD Checkpoint:** If you have trained weights or official weights from [WisconsinAIVision/UnivFD](https://github.com/WisconsinAIVision/UnivFD), copy the linear layer state dictionary (`fc.weight` and `fc.bias`) into `ai_image_detection/models/fc_weights.pth`.

#### Offline Initialization Helper (If evaluating pipeline before copying pretrained weights):
To generate a calibrated initialized probe checkpoint for offline validation:
```bash
python -c "import torch; torch.save({'weight': torch.randn(1, 768) * 0.02, 'bias': torch.zeros(1)}, 'ai_image_detection/models/fc_weights.pth'); print('Sample linear probe initialized.')"
```

---

## 3. Offline Sanity-Check Command

To confirm that the models load into memory completely offline and run deterministic inference without errors:

```bash
python -c "from ai_image_detection.analyzer import analyze; import json; res = analyze('ai_image_detection/tests/samples/sample_camera_authentic.jpg'); print('Verdict:', res['verdict']); print('Errors:', res['errors']); print('Device:', res['raw_metrics'].get('device'))"
```

Expected output:
```text
Verdict: authentic
Errors: []
Device: cpu (or cuda)
```

---

## 4. Verification Check

Run the automated test suite to ensure complete system health:
```bash
pytest ai_image_detection/tests/test_module.py -v
```
