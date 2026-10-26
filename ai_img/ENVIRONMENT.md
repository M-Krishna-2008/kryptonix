# Environment Specification: PS-05 AI Image Detection

This document specifies the exact execution environment, runtime matrix, and dependency constraints validated during the clean-room portability audit on Windows 10/11.

---

## 1. Core Runtime Matrix

| Component | Tested Version | Minimum Required | Notes |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 11 Home (64-bit) | Windows 10 build 1809+ (64-bit) | Requires x64 architecture. |
| **Python** | `3.10.11` | `3.10.0` – `<3.12.0` | 3.10 is the platform-wide standard across all 4 forensic modules. |
| **PyTorch (CUDA)** | `2.6.0+cu124` | `2.2.0` | Automatically provisioned when NVIDIA GPU is detected. |
| **PyTorch (CPU)** | `2.6.0+cpu` | `2.2.0` | Fallback build if no GPU or driver present. |
| **Torchvision** | `0.21.0+cu124` / `0.21.0+cpu` | `0.17.0` | Matches PyTorch build. |
| **NumPy** | `2.2.6` | `1.24.0` | Fully compatible with NumPy 1.26.4 if sibling modules require NumPy 1.x. |
| **Pillow** | `12.3.0` | `10.0.0` | Image decoding and multi-crop preparation. |
| **FastAPI** | `0.115.6` | `0.110.0` | Module REST router and standalone ASGI host. |
| **Uvicorn** | `0.34.0` | `0.28.0` | ASGI web server. |
| **OpenAI CLIP** | `1.0.1` (`master.zip`) | `1.0.0` | Installed directly from GitHub ZIP archive (no Git CLI needed). |

---

## 2. Hardware & Architecture Compatibility

- **64-bit Architecture:** Required. 32-bit Windows is strictly unsupported by modern PyTorch and CLIP.
- **Disk Storage:** Minimum 10 GB free space recommended (PyTorch CUDA wheel is ~2.5 GB; model weights are ~933 MB; virtual environment is ~4.5 GB).
- **RAM:** Minimum 8 GB RAM (16 GB recommended for multi-crop grid feature extraction).
- **GPU Acceleration:**
  - Supported: NVIDIA GPUs with CUDA capabilities `sm_50` through `sm_90` (Maxwell through Ada Lovelace).
  - Newer GPUs (e.g. RTX 50-series / Blackwell `sm_120`): Handled via seamless automatic CPU fallback in `analyzer.py` without user intervention or crash.
  - Non-NVIDIA / Integrated Intel/AMD: Fully supported in CPU mode.

---

## 3. Pinned Dependencies (`requirements-lock.txt`)

```text
annotated-types==0.8.0
anyio==4.15.1
certifi==2026.10.23
charset-normalizer==3.5.2
click==8.5.0
colorama==0.4.6
exceptiongroup==1.3.1
fastapi==0.115.6
filelock==3.32.3
fsspec==2026.7.0
ftfy==6.3.1
h11==0.16.0
httpcore==1.0.9
httptools==0.9.0
httpx==0.28.1
idna==3.20
iniconfig==2.3.1
Jinja2==3.1.6
MarkupSafe==3.0.3
mpmath==1.3.0
networkx==3.4.2
numpy==2.2.6
opencv-python==5.0.0.93
packaging==26.3
pillow==12.3.0
pillow-heif==1.8.1
pluggy==1.7.0
pydantic==2.14.1
pydantic_core==2.50.1
Pygments==2.21.0
pytest==9.1.1
python-dotenv==1.2.4
python-multipart==0.0.20
PyYAML==6.0.3
regex==2026.9.29
requests==2.34.2
scipy==1.15.3
starlette==0.41.3
sympy==1.13.1
tomli==2.5.0
tqdm==4.70.1
typing_extensions==4.16.0
typing-inspection==0.4.4
urllib3==2.8.0
uvicorn==0.34.0
watchfiles==1.3.0
wcwidth==0.9.3
websockets==16.1.1
https://github.com/openai/CLIP/archive/master.zip
```
