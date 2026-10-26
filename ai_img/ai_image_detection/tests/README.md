# Test Suite and Forensic Sample Images (`tests/`)

This directory contains automated unit tests, synthetic sample generators, and evaluation scripts for the `ai_image_detection` (UnivFD) module.

---

## 1. Directory Structure

```text
tests/
├── README.md               # This guide
├── test_module.py          # Pytest unit tests (shapes, determinism, decision branches, errors)
├── generate_samples.py     # Generates offline synthetic test samples
├── run_samples.py          # Runs analysis on all sample images and outputs results table
└── samples/                # Sample test images directory
    ├── sample_camera_authentic.jpg   # Real camera capture with Canon EXIF metadata
    ├── sample_ai_tampered.png        # Synthetic image with AI generator prompt tags
    ├── sample_compressed_social.jpg  # Compressed social-media re-upload (JPEG Q < 75)
    └── sample_blurry_small.jpg       # Small/blurry image (<256px or Laplacian var < 100)
```

---

## 2. Where to Place Your Own Forensic Samples

To evaluate your own real and AI-generated cases, place images into `tests/samples/`:

| Filename Pattern | Category | Expected Behavior |
| :--- | :--- | :--- |
| `real_*.jpg` or `sample_camera_*.jpg` | Genuine Camera Photos | Evaluated against `camera_photo` thresholds (Real $\le 0.20$, Fake $\ge 0.80$). Requires genuine EXIF. |
| `fake_*.png` or `sample_ai_*.png` | AI-Generated (Midjourney, DALL-E, SD, Flux) | Evaluated against `ai_render` or provenance tags. Triggers `likely_tampered`. |
| `social_*.jpg` or `sample_compressed_*.jpg` | Social Media Re-uploads | Evaluated against `social_media_reupload` thresholds (Real $\le 0.10$, Fake $\ge 0.90$). |
| `screenshot_*.png` | Screen Captures | Evaluated against `screenshot` thresholds (Real $\le 0.05$, Fake $\ge 0.95$). |
| `small_*.jpg` | Insufficient Quality | Triggers `small_or_blurry` heuristic; yields `inconclusive` verdict. |

---

## 3. Running Automated Tests

Run unit tests via `pytest`:
```bash
pytest tests/test_module.py -v
```

---

## 4. Running Sample Evaluation Table

To analyze all sample images in `tests/samples/` and print a forensic ASCII report table:
```bash
python tests/run_samples.py
```
