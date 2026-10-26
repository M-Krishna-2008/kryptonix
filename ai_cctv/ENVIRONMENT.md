# Environment Specification: PS-05 AI CCTV Detection Module

## 1. Verified Python Environment
- **Tested Python Versions**: Python 3.10.11 and Python 3.11.9 (64-bit AMD64).
- **Recommended Standard for Multi-Module Merge**: Python 3.10 (64-bit).
- **Architecture**: Windows 10 / Windows 11 (x86_64 / AMD64 only; 32-bit is not supported).

---

## 2. Hardware Acceleration & Fallback Behavior

### GPU Mode (NVIDIA CUDA)
- **Detected via**: `nvidia-smi` presence or PowerShell WMI `Win32_VideoController` containing `NVIDIA`.
- **PyTorch Build**: `torch==2.6.0+cu124` and `torchvision==0.21.0+cu124` from `https://download.pytorch.org/whl/cu124`.
- **Runtime Behavior**: Model weights automatically move to `cuda:0` when available. Inference speed is ~120-250 FPS on modern RTX GPUs (e.g., RTX 4050/3060/4090), allowing real-time processing of high-framerate CCTV evidence.

### CPU Mode (Universal Windows Fallback)
- **Detected via**: Absence of NVIDIA GPU or missing CUDA drivers.
- **PyTorch Build**: `torch==2.6.0+cpu` and `torchvision==0.21.0+cpu` from `https://download.pytorch.org/whl/cpu`.
- **Runtime Behavior**: Automatically moves tensors to `cpu` with PyTorch multi-threading (`torch.set_num_threads`). Inference speed is ~15-35 FPS on modern quad-core/octa-core Intel/AMD CPUs.
- **Portability Guarantee**: No CUDA DLL errors will ever occur on CPU-only machines.

---

## 3. Pinned Dependencies and Purpose

| Package | Version | Purpose |
|---|---|---|
| `torch` | `==2.6.0` | Deep learning tensor framework for YOLO model execution |
| `torchvision` | `==0.21.0` | Vision utilities and transforms |
| `ultralytics` | `==8.4.185` | YOLO11 architecture, model loader, and inference engine |
| `ultralytics-thop` | `==2.2.3` | Flops and profile calculation for Ultralytics |
| `av` (PyAV) | `==18.1.0` | Direct FFmpeg C-library binding; decodes MP4/H.264 without external ffmpeg.exe |
| `opencv-python` | `==4.11.0.86` | Computer vision transforms, tile slicing, and image processing |
| `numpy` | `==1.26.4` | High-performance numerical arrays and matrix operations |
| `scipy` | `==1.17.1` | Scientific computing, temporal window metrics, filtering |
| `scikit-learn` | `==1.9.1` | Logistic Regression calibration (Platt scaling) |
| `matplotlib` | `==3.11.2` | Headless chart generation (`Agg` backend) for forensic evidence plots |
| `PyYAML` | `==6.0.3` | YAML configuration parsing for calibration parameters |
| `fastapi` | `==0.162.0` | REST API framework implementing PS-05 endpoints |
| `uvicorn` | `==0.54.0` | Production ASGI web server |
| `pydantic` | `==2.14.1` | Strict JSON schema validation for forensic reports |
| `pydantic_core` | `==2.50.1` | Core Rust-accelerated Pydantic parser |
| `python-multipart` | `==0.0.32` | Streaming large evidence video uploads (>2GB) |
| `starlette` | `==1.9.0` | ASGI application foundation, static file serving, HTTP routing |
| `pytest` | `==9.1.1` | Automated test suite execution |
| `pillow` | `==12.3.0` | Image format loading and validation |
| `requests` | `==2.34.2` | HTTP client for remote health checks and tests |

---

## 4. Microsoft Visual C++ Runtime Requirement
PyTorch, OpenCV, and PyAV on Windows require the **Microsoft Visual C++ 2015-2022 Redistributable (x64)** (`MSVCP140.dll`, `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`).
- Detected via: `reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed`
- Automated Installation: The launcher installs it via `winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements`.
