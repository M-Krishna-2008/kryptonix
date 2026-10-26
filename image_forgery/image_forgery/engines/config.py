"""
Configuration and threshold definitions for the image_forgery module.
Single Deep Engine: TruFor + Classical Forensic Suite.
All thresholds are configurable via environment variables with safe defaults.
"""

import os
from pathlib import Path

# Paths
MODULE_NAME = "image_forgery"
MODULE_ROOT = Path(__file__).resolve().parent.parent

# Storage directories (configurable via env vars)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(MODULE_ROOT / "uploads")))
ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", str(MODULE_ROOT / "artifacts")))

# Intake constraints
MAX_IMAGE_MB = int(os.environ.get("MAX_IMAGE_MB", "50"))
MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", "100000000"))  # 100 MP
MIN_IMAGE_SIDE = int(os.environ.get("MIN_IMAGE_SIDE", "64"))
RELIABILITY_MIN_SIDE = int(os.environ.get("RELIABILITY_MIN_SIDE", "256"))

# Subprocess runner settings
SUBPROCESS_TIMEOUT_SEC = int(os.environ.get("SUBPROCESS_TIMEOUT_SEC", "300"))

# Thresholds
DEFAULT_MASK_THRESHOLD = float(os.environ.get("DEFAULT_MASK_THRESHOLD", "0.5"))
DEFAULT_MAX_SIDE = int(os.environ.get("DEFAULT_MAX_SIDE", "1024"))
DEFAULT_ELA_QUALITY = int(os.environ.get("DEFAULT_ELA_QUALITY", "90"))
DEFAULT_MIN_REGION_AREA_FRAC = float(os.environ.get("DEFAULT_MIN_REGION_AREA_FRAC", "0.005"))
DEFAULT_CONF_THRESHOLD = float(os.environ.get("DEFAULT_CONF_THRESHOLD", "0.35"))

# TruFor Score Thresholds (Three calibrated verdicts: Likely Authentic, Inconclusive, Likely Manipulated)
# Tune these constants to calibrate module sensitivity
TRUFOR_AUTHENTIC_THRESHOLD = float(os.environ.get("TRUFOR_AUTHENTIC_THRESHOLD", "0.35"))
TRUFOR_TAMPERED_THRESHOLD = float(os.environ.get("TRUFOR_TAMPERED_THRESHOLD", "0.60"))

# Legacy aliases for backward compatibility
TRUFOR_LOW_SCORE_THRESHOLD = TRUFOR_AUTHENTIC_THRESHOLD
TRUFOR_HIGH_SCORE_THRESHOLD = TRUFOR_TAMPERED_THRESHOLD

# Box filtering constraints to reject edge artifacts
# Boxes touching image borders or with aspect ratio > 1:15 are dropped as artifacts
BORDER_MARGIN_PIXELS = int(os.environ.get("BORDER_MARGIN_PIXELS", "2"))
MAX_BOX_ASPECT_RATIO = float(os.environ.get("MAX_BOX_ASPECT_RATIO", "15.0"))

# Input quality warning thresholds
QUALITY_WARN_MAX_FILE_SIZE_KB = float(os.environ.get("QUALITY_WARN_MAX_FILE_SIZE_KB", "50.0"))
QUALITY_WARN_MIN_SHORT_SIDE_PX = int(os.environ.get("QUALITY_WARN_MIN_SHORT_SIDE_PX", "500"))

# Reliability gating & verdict confidence caps
LOW_JPEG_QUALITY_THRESHOLD = int(os.environ.get("LOW_JPEG_QUALITY_THRESHOLD", "65"))
AUTH_CONFIDENCE_CAP = float(os.environ.get("AUTH_CONFIDENCE_CAP", "0.75"))
TAMPERED_CONFIDENCE_CAP = float(os.environ.get("TAMPERED_CONFIDENCE_CAP", "0.85"))
