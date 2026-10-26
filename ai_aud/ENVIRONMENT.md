# PS-05 Audio Forensics Environment & Reproduction Guide

## System Specifications
- **Operating System**: Windows 11 64-bit (build 26100+)
- **Python Version**: Python 3.10.11 (64-bit, installed via `winget install Python.Python.3.10` or official installer)
- **C++ Compiler**: Microsoft Visual C++ Build Tools 2019/2022 (v142/v143)

---

## Verified Working Package Versions
Pinned in `requirements-lock.txt`:

| Package | Pinned Version | Purpose / Compatibility Notes |
| :--- | :--- | :--- |
| **Python** | `3.10.11` | Fairseq requires Python <= 3.10; fails on 3.11+ |
| **pip** | `24.0` | Pinned `< 24.1` to avoid fairseq/omegaconf metadata wheel resolution bug |
| **torch** | `2.14.1+cpu` / `2.5.1+cu121` | CPU inference verified first; auto-detects CUDA with `nvidia-smi` |
| **torchaudio** | `2.11.0+cpu` / `2.5.1+cu121` | Audio tensor operations |
| **numpy** | `1.26.4` | Pinned `< 2.0.0` (fairseq references `np.float` / `np.int` deprecated in NumPy 2.x) |
| **scipy** | `1.15.3` | STFT and polyphase resampling filter operations |
| **soundfile** | `0.14.0` | Primary audio decoding engine (libsndfile backend) |
| **av** | `17.1.0` | Universal container decoder (PyAV bundles FFmpeg statically) |
| **librosa** | `0.11.0` | Secondary acoustic analysis fallback |
| **mutagen** | `1.48.1` | Audio metadata & editing tool tag inspection |
| **matplotlib** | `3.10.0` | Headless visual evidence generation (Agg backend) |
| **fastapi** | `0.115.0` | Asynchronous REST API server |
| **uvicorn** | `0.32.0` | ASGI production application server |
| **python-multipart** | `0.0.12` | Multipart/form-data upload streaming |
| **pydantic** | `2.10.0` | Standard Result Format schema validation |
| **pyyaml** | `6.0.2` | Thresholds & configuration parsing |
| **pytest** | `8.3.0` | Test suite execution |
| **pyttsx3** | `2.99` | Windows SAPI5 synthetic speech generator for tests |

---

## Fairseq Integration & Checkpoints
- **Reference Repository**: [github.com/TakHemlata/SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing)
- **Fairseq Commit**: `a54021305d6b3c4c5959ac9395135f63202db8f1`
- **Hugging Face Model Card**: [huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST](https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST)
- **Paper Reference**: Hemlata Tak et al., *"Automatic speaker verification spoofing and deepfake detection using wav2vec 2.0 and data augmentation"*, Odyssey 2022 (arXiv:2202.12233).

### Model Checkpoints
1. `xlsr2_300m.pt` (~1.18 GB)
   - Source: `https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt`
   - Destination: `audio_forensics/models/xlsr2_300m.pt`
2. `LA_model.pth` (~1.23 GB)
   - Source: `https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST/resolve/main/LA_model.pth`
   - Destination: `audio_forensics/models/LA_model.pth`

---

## Verified Score Direction
- **Metric**: Bona-fide Logit (Index 1 of the AASIST output layer)
- **Direction**:
  - `Logit > +1.5`: Authentic / genuine human speech
  - `Logit < -1.5`: Spoofed / AI-generated / synthesized speech
  - `[-1.5, +1.5]`: Uncertain band (further investigation recommended)
- **Note**: The metric is an unbounded logit, **NOT a probability**. Never display or represent it as a percentage.
