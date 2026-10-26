# PS-05 Unified AI Forensics Platform - License & Third-Party Attribution Notes

## Repository License Overview
This repository contains the integration architecture, gateway proxy, web interface, orchestration scripts, and testing harnesses for the **PS-05 AI Forensics Platform**.

> **IMPORTANT NOTICE REGARDING MODELS AND DATASETS:**
> Model checkpoints exceeding 25 MB and raw training/benchmark datasets are **NOT redistributed** in this repository. All models are automatically retrieved at initial launcher setup from their respective upstream canonical research repositories, or can be mounted offline via `make_offline_bundle.bat`.

---

## Component & Model Licenses

### 1. Audio Forensics (`ai_aud`)
* **XLS-R 300M Backbone**: Developed by Meta AI / Fairseq. Released under the [Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0)](https://github.com/facebookresearch/fairseq/blob/main/LICENSE).
* **W2V2-AASIST Acoustic Classifier**: Developed by the SpeechAntiSpoofingBenchmarks team and ASVspoof consortium. Licensed under the [MIT License / ASVspoof Evaluation Agreement](https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST).
* **PyAV / FFmpeg Codecs**: Bundled via binary PyAV bindings under LGPL v2.1+.

### 2. AI Image Detection (`ai_img`)
* **CLIP ViT-L/14 Feature Extractor**: Developed by OpenAI. Released under the [MIT License](https://github.com/openai/CLIP/blob/main/LICENSE).
* **Universal Fake Detect (UnivFD)**: Developed by Yuheng Li et al. Linear probe weights and inference logic released under the [MIT License](https://github.com/Yuheng-Li/UniversalFakeDetect/blob/main/LICENSE).

### 3. Photoshop Forgery & Tamper Localization (`image_forgery`)
* **TruFor Engine**: Developed by the Image Processing Research Group (GRIP) at the University of Naples Federico II (Fabrizio Guillaro, Denisa Bunk, Davide Cozzolino, Luisa Verdoliva). Released under the [TruFor Research and Informational Use License](file:///image_forgery/image_forgery/third_party/TruFor/LICENSE.txt) strictly for nonprofit, academic, and forensic evaluation.

### 4. CCTV Video Tamper Forensics (`ai_cctv`)
* **Ultralytics YOLO11s**: Developed by Ultralytics LLC. Released under the [GNU Affero General Public License v3.0 (AGPL-3.0)](https://github.com/ultralytics/ultralytics/blob/main/LICENSE).
* **Trained CCTV Weights (`best.pt`)**: Locally trained forensic weights developed specifically for PS-05 CCTV anomaly detection.

---

## Dataset Notice
All benchmark datasets (e.g. ASVspoof, FaceForensics++, UCF-Crime, CASIA, Coverage, and private surveillance recordings) are excluded from this repository to safeguard privacy, copyright, and distribution compliance. Only synthetic test fixtures generated purely by local mathematical scripts are maintained for CI/CD smoke validation.
