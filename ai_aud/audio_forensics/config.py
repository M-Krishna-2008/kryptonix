from __future__ import annotations
import os
from pathlib import Path
import yaml

# Base Module Paths (always relative to module, never rely on cwd)
MODULE_DIR = Path(__file__).resolve().parent
ROOT_DIR = MODULE_DIR.parent
CONFIGS_DIR = MODULE_DIR / "configs"
MODELS_DIR = MODULE_DIR / "models"
STATIC_DIR = MODULE_DIR / "static"

# Shared Upload, Artifacts and Cache Directories (configurable via env)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", ROOT_DIR / "uploads")).resolve()
ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", ROOT_DIR / "artifacts" / "audio_forensics")).resolve()
CACHE_DIR = Path(os.environ.get("CACHE_DIR", ROOT_DIR / "cache")).resolve()

# Ensure standard directories exist
for directory in [UPLOAD_DIR, ARTIFACT_DIR, CACHE_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Model checkpoints
XLSR_MODEL_PATH = MODELS_DIR / "xlsr2_300m.pt"
AASIST_MODEL_PATH = MODELS_DIR / "LA_model.pth"

# Upstream download URLs
XLSR_DOWNLOAD_URL = "https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt"
AASIST_DOWNLOAD_URL = "https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST/resolve/main/LA_model.pth"

# VERIFIED SCORE DIRECTION:
# The raw output is the bona-fide logit (index 1 of the AASIST output layer).
# Higher logit = authentic / genuine speech.
# Lower logit = spoofed / synthetic speech.
SCORE_DIRECTION = "higher_is_authentic"
RAW_METRIC_NAME = "bona_fide_logit"

# Audio Preprocessing & Windowing Constants
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 64600  # Exactly 64,600 samples (~4.0375s at 16kHz)
HOP_RATIO = 0.5         # 50% overlap
HOP_SAMPLES = int(WINDOW_SAMPLES * HOP_RATIO)  # 32,300 samples (~2.01875s)
MAX_DURATION_SEC = 600.0  # 10 minutes maximum duration
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB limit
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "4"))

DEFAULT_THRESHOLDS = {
    "low_threshold": -2.5,
    "high_threshold": 1.5,
    "suspicious_margin": 0.5,
    "borderline_margin": 0.5,
    "whole_clip_fraction_low": 0.60,
    "whole_clip_min_windows": 3,
    "partial_min_consecutive_low": 2,
    "partial_min_low_windows": 3,
    "partial_min_fraction_low": 0.25,
    "partial_min_total_windows": 5,
    "min_run_seconds": 6.0,
    "fraction_low_authentic": 0.05,
    "vad_speech_ratio_threshold": 0.50,
    "vad_min_speech_windows": 2,
    "lossy_confidence_cap": 0.70,
    # Backward compatibility aliases
    "fraction_low_clip": 0.60,
    "fraction_low_segment": 0.25,
}


def load_thresholds(codec_class: str | None = None) -> dict:
    """
    Loads thresholds from configs/thresholds.yaml with fallback to DEFAULT_THRESHOLDS.
    If codec_class is specified ('lossless', 'lossy_high_bitrate', 'lossy_low_bitrate'),
    applies the specific thresholds defined for that codec profile.
    """
    config_file = CONFIGS_DIR / "thresholds.yaml"
    merged = dict(DEFAULT_THRESHOLDS)
    raw_yaml: dict = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "thresholds" in data:
                    raw_yaml = data["thresholds"]
                    merged.update(raw_yaml)
        except Exception:
            pass

    # If codec_class profile exists, apply codec-specific overrides
    codec_profiles = raw_yaml.get("codec_classes", {}) if raw_yaml else {}
    if codec_class and codec_class in codec_profiles:
        profile = codec_profiles[codec_class]
        if isinstance(profile, dict):
            for k, v in profile.items():
                merged[k] = v
            merged["applied_codec_class"] = codec_class

    return merged

