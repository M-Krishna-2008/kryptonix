# Runtime Environment Specifications: `image_forgery`

## 1. Operating System
- **Tested Operating System**: Microsoft Windows 10 / 11 (64-bit AMD64)
- **Minimum OS Version**: Windows 10 Build 19041+ or Windows 11
- **File System**: NTFS, support for paths with spaces and long paths enabled

## 2. Python Environment
- **Recommended Python Version**: Python 3.10.x (e.g. 3.10.11)
- **Supported Python Range**: `>=3.10, <3.14`
- **Virtual Environment**: `.venv` isolated virtual environment created via `python -m venv .venv`

## 3. Core Framework & Model Acceleration
- **PyTorch**: `2.14.1` (or `>=2.1.0`)
- **TorchVision**: `0.29.1` (or `>=0.16.0`)
- **Hardware Acceleration**:
  - **NVIDIA GPU Mode**: Requires NVIDIA driver + CUDA 12.8 wheel index (`https://download.pytorch.org/whl/cu128`) for RTX 50-series (Blackwell) / RTX 40-series / RTX 30-series.
  - **CPU Mode**: Standard PyTorch wheel (`pip install torch torchvision`). Automatically selected if `nvidia-smi` is not detected.

## 4. Key Scientific & Web Dependencies
- **NumPy**: `2.5.4` (compatible with `numpy>=1.22`)
- **OpenCV**: `opencv-python-headless==5.0.0.93` (headless build avoids GUI/X11 dependency issues)
- **Pillow**: `13.0.0`
- **SciPy**: `1.18.1`
- **Timm**: `1.0.30` (Segformer backbone implementation)
- **YACS**: `0.1.8` (TruFor experiment configuration)
- **Piexif**: `1.1.3` (EXIF header parsing)
- **FastAPI**: `0.162.0`
- **Uvicorn**: `0.54.0`
- **Pydantic**: `2.14.1`

## 5. System Dependencies
- **Microsoft Visual C++ 2015-2022 Redistributable (x64)** (`vcruntime140.dll`): Required by PyTorch C++ extensions.
- **Node.js**: NOT required (vanilla HTML/CSS/JS).
- **FFmpeg**: NOT required (still image processing only).
- **Git**: NOT required (TruFor is vendored locally in `third_party/TruFor/`).
