# Module Changes & Adaptations Log

This document records all modifications made to module directories.
In strict accordance with the architecture requirements, **zero model internals were rewritten**.

## 1. `image_forgery`
- **Environment Relocation Fix**: Corrected host Python binary reference in `image_forgery/image_forgery/.venv/pyvenv.cfg` from previous developer's path (`C:\Users\Subha\...`) to active environment path (`C:\Users\galah\...`).
- **Dependencies Provisioning**: Installed `timm` (1.0.30), `yacs` (0.1.8), and `piexif` (1.1.3) into `image_forgery/image_forgery/.venv` to satisfy `requirements.txt`.
- **Model code changes**: None.

## 2. `ai_cctv`
- **Environment Initialization**: Initialized clean `.venv` using Python 3.10 as specified in `MODULE_MANIFEST.json` and installed pinned dependencies from `requirements.txt`.
- **Model code changes**: None.

## 3. `ai_aud`
- **Model code changes**: None. Existing `.venv` (Python 3.10.11 + fairseq + torch 2.14.1+cpu) verified functional.

## 4. `ai_img`
- **Model code changes**: None. Existing `.venv` (Python 3.13 + CLIP ViT-L/14) verified functional.
