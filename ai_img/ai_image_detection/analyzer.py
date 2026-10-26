"""
Core logic for the ai_image_detection forensic module.
Universal Fake Detect (UnivFD) implementation using frozen CLIP ViT-L/14 + linear probe.
100% local, zero cloud dependencies. Adheres strictly to PS-05 Integration Contract.
"""

import os
import sys
import json
import hashlib
import time
import math
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont
import yaml

# Optional HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

import torch
import torch.nn as nn

# Local helper imports
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from decide import evaluate_decision, load_thresholds

# Model paths
MODELS_DIR = MODULE_DIR / "models"
CLIP_WEIGHTS_PATH = MODELS_DIR / "clip" / "ViT-L-14.pt"
PROBE_WEIGHTS_PATH = MODELS_DIR / "fc_weights.pth"
CONFIGS_DIR = MODULE_DIR / "configs"
CALIBRATION_PATH = CONFIGS_DIR / "calibration.yaml"
THRESHOLDS_PATH = CONFIGS_DIR / "thresholds.yaml"
CACHE_DIR = MODULE_DIR / "cache"


# ---------------------------------------------------------------------------
# Lazy Singleton Model Manager
# ---------------------------------------------------------------------------
class ModelManager:
    _instance = None

    def __init__(self):
        self.clip_model = None
        self.linear_probe = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.use_fp16 = self.device == "cuda"
        self.load_error = None
        self.is_loaded = False

    @classmethod
    def get_instance(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance

    def load_models(self) -> Tuple[bool, Optional[str]]:
        """
        Loads frozen CLIP ViT-L/14 and linear probe weights once.
        Returns (success: bool, error_message: str | None).
        NEVER attempts to download weights from the internet.
        """
        if self.is_loaded:
            return True, None
        if self.load_error:
            return False, self.load_error

        # Verify weights exist locally
        clip_target = CLIP_WEIGHTS_PATH
        if not clip_target.is_file() and (MODELS_DIR / "ViT-L-14.pt").is_file():
            clip_target = MODELS_DIR / "ViT-L-14.pt"

        missing = []
        if not clip_target.is_file():
            missing.append(
                f"CLIP ViT-L/14 weights not found at '{CLIP_WEIGHTS_PATH.relative_to(MODULE_DIR)}'. "
                f"Download 'ViT-L-14.pt' and place it in 'models/clip'. See setup_model.md."
            )
        if not PROBE_WEIGHTS_PATH.is_file():
            missing.append(
                f"Linear probe weights not found at '{PROBE_WEIGHTS_PATH.relative_to(MODULE_DIR)}'. "
                f"Place 'fc_weights.pth' in 'models'. See setup_model.md."
            )

        if missing:
            self.load_error = " | ".join(missing)
            return False, self.load_error

        try:
            import clip

            # Load CLIP locally without network
            model, _ = clip.load(str(clip_target), device=self.device, jit=False)
            model.eval()
            for p in model.parameters():
                p.requires_grad = False
            self.clip_model = model

            # Load Linear Probe: 768 -> 1
            probe = nn.Linear(768, 1)
            probe_state = torch.load(PROBE_WEIGHTS_PATH, map_location=self.device)
            if isinstance(probe_state, dict):
                if "weight" in probe_state:
                    probe.load_state_dict(probe_state)
                elif "state_dict" in probe_state:
                    probe.load_state_dict(probe_state["state_dict"])
                else:
                    probe.load_state_dict(probe_state)
            elif isinstance(probe_state, nn.Module):
                probe = probe_state

            probe.to(self.device).eval()
            for p in probe.parameters():
                p.requires_grad = False
            self.linear_probe = probe

            self.is_loaded = True
            return True, None
        except Exception as e:
            self.load_error = f"Failed to initialize models from local weights: {str(e)}"
            return False, self.load_error


# ---------------------------------------------------------------------------
# Stage 1: Ingestion & Image Metadata
# ---------------------------------------------------------------------------
def compute_sha256(file_path: Path) -> str:
    """Calculates SHA-256 hash of file buffer for forensic chain-of-custody."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def estimate_jpeg_quality(image: Image.Image) -> Optional[int]:
    """
    Estimates JPEG compression quality (1-100) from luminance quantization table (DQT).
    Uses standard IJG (Independent JPEG Group) baseline quantization table matrix.
    """
    if not hasattr(image, "quantization") or not image.quantization:
        return None

    try:
        # Standard IJG 50% luminance table
        std_lum_q = [
            16, 11, 10, 16, 24, 40, 51, 61,
            12, 12, 14, 19, 26, 58, 60, 55,
            14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77,
            24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101,
            72, 92, 95, 98, 112, 100, 103, 99
        ]
        q_table = image.quantization.get(0)
        if not q_table or len(q_table) < 64:
            return None

        # Calculate average scaling factor across quantization matrix
        scales = []
        for i in range(64):
            if std_lum_q[i] > 0 and i < len(q_table):
                scales.append(q_table[i] / std_lum_q[i])
        
        avg_scale = float(np.median(scales)) if scales else 1.0

        if avg_scale <= 0:
            return 100
        elif avg_scale <= 1.0:
            quality = int(round((200.0 - avg_scale * 100.0) / 2.0))
        else:
            quality = int(round(5000.0 / (avg_scale * 100.0)))

        return max(1, min(100, quality))
    except Exception:
        return None


def ingest_image(file_path: Path) -> Tuple[Optional[Image.Image], Dict[str, Any], Optional[str]]:
    """
    Stage 1: Ingests image with Pillow.
    Handles EXIF rotation, converts to RGB, extracts format, size, and estimated JPEG quality.
    """
    try:
        if not file_path.is_file():
            return None, {}, f"File does not exist: {file_path}"

        raw_size = file_path.stat().st_size
        if raw_size == 0:
            return None, {}, "File is empty (0 bytes)."

        with Image.open(file_path) as raw_img:
            img_format = raw_img.format or file_path.suffix.lstrip(".").upper()
            jpeg_quality = estimate_jpeg_quality(raw_img) if img_format == "JPEG" else None
            
            # Apply EXIF rotation transpose
            try:
                img = ImageOps.exif_transpose(raw_img)
            except Exception:
                img = raw_img.copy()

            # Convert color space gracefully to RGB
            if img.mode != "RGB":
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    # White background for transparency
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    alpha_img = img.convert("RGBA")
                    bg.paste(alpha_img, mask=alpha_img.split()[3])
                    img = bg
                else:
                    img = img.convert("RGB")

            info = {
                "format": img_format,
                "width": img.width,
                "height": img.height,
                "file_size": raw_size,
                "jpeg_quality": jpeg_quality,
            }
            return img, info, None
    except Exception as e:
        return None, {}, f"Failed to ingest image: {str(e)}"


# ---------------------------------------------------------------------------
# Stage 2: Pre-process (Multi-Crop 224x224 Grid with No Resizing)
# ---------------------------------------------------------------------------
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32).reshape(3, 1, 1)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32).reshape(3, 1, 1)


def generate_crops(img: Image.Image) -> Tuple[List[Image.Image], List[Tuple[int, int, int, int]], bool]:
    """
    Generates up to 9 crops (3x3 grid) of 224x224 with NO resizing.
    If image < 224px, pads and sets is_padded=True.
    Returns (crops, crop_boxes, is_padded).
    """
    w, h = img.width, img.height
    is_padded = False

    if w < 224 or h < 224:
        is_padded = True
        pad_w = max(224, w)
        pad_h = max(224, h)
        padded = Image.new("RGB", (pad_w, pad_h), (128, 128, 128))
        paste_x = (pad_w - w) // 2
        paste_y = (pad_h - h) // 2
        padded.paste(img, (paste_x, paste_y))
        crop = padded.crop((0, 0, 224, 224))
        return [crop], [(0, 0, 224, 224)], True

    # 3x3 grid coordinates
    xs = sorted(list({0, (w - 224) // 2, w - 224}))
    ys = sorted(list({0, (h - 224) // 2, h - 224}))

    crops = []
    boxes = []
    for y in ys:
        for x in xs:
            box = (x, y, x + 224, y + 224)
            crops.append(img.crop(box))
            boxes.append(box)

    return crops, boxes, False


def preprocess_crop_to_tensor(crop: Image.Image) -> torch.Tensor:
    """
    Converts a 224x224 PIL Image to CLIP normalized tensor: shape (3, 224, 224).
    """
    arr = np.array(crop, dtype=np.float32) / 255.0  # (224, 224, 3)
    arr = arr.transpose(2, 0, 1)                    # (3, 224, 224)
    norm = (arr - CLIP_MEAN) / CLIP_STD
    return torch.from_numpy(norm).float()


# ---------------------------------------------------------------------------
# Stage 6: Photo-Type Detection (Forensic Heuristics)
# ---------------------------------------------------------------------------
def compute_laplacian_variance(img: Image.Image) -> float:
    """Computes blur metric (variance of Laplacian). Lower = blurrier."""
    gray = np.array(img.convert("L"), dtype=np.float32)
    # 3x3 Laplacian kernel
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    
    # Convolution via 2D slicing
    h, w = gray.shape
    if h < 5 or w < 5:
        return 0.0
    
    lap = (
        gray[0:h-2, 1:w-1] + gray[2:h, 1:w-1] +
        gray[1:h-1, 0:w-2] + gray[1:h-1, 2:w] -
        4.0 * gray[1:h-1, 1:w-1]
    )
    return float(np.var(lap))


def detect_photo_type(
    img: Image.Image,
    info: Dict[str, Any],
    file_bytes: bytes,
    exif_tags: Dict[str, Any]
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Classifies image into one of:
    - small_or_blurry
    - screenshot
    - edited
    - social_media_reupload
    - camera_photo
    - ai_render
    """
    w, h = info["width"], info["height"]
    jpeg_q = info.get("jpeg_quality")
    lap_var = compute_laplacian_variance(img)

    details = {
        "laplacian_variance": round(lap_var, 2),
        "jpeg_quality": jpeg_q,
        "resolution": f"{w}x{h}",
        "aspect_ratio": round(w / max(1, h), 3)
    }

    # 1. small_or_blurry
    if min(w, h) < 256 or lap_var < 100.0:
        reason = f"Short side < 256px ({min(w, h)}px) or Laplacian blur variance ({lap_var:.1f}) < 100."
        return "small_or_blurry", reason, details

    # 2. edited: software tags in EXIF
    software_keys = ["Software", "ProcessingSoftware", "History", "HostComputer"]
    editing_tools = [
        "photoshop", "lightroom", "gimp", "canva", "snapseed", "photoscape",
        "affinity", "pixlr", "paint.net", "corel", "vsco", "capture one"
    ]
    detected_software = []
    for k, v in exif_tags.items():
        v_str = str(v).lower()
        for tool in editing_tools:
            if tool in v_str:
                detected_software.append(tool)

    if detected_software:
        details["editing_software"] = list(set(detected_software))
        reason = f"Editing software metadata detected ({', '.join(set(detected_software))})."
        return "edited", reason, details

    # 3. screenshot: standard display resolutions + NO camera EXIF
    has_camera_exif = any(tag in exif_tags for tag in ["Make", "Model", "FocalLength", "FNumber", "ISOSpeedRatings"])
    common_screen_resolutions = {
        (1920, 1080), (1080, 1920),
        (2560, 1440), (1440, 2560),
        (3840, 2160), (2160, 3840),
        (1366, 768), (768, 1366),
        (1440, 900), (900, 1440),
        (1280, 720), (720, 1280),
        (1280, 800), (800, 1280),
        (1170, 2532), (2532, 1170),
        (1080, 2400), (2400, 1080),
        (1080, 2340), (2340, 1080),
        (1179, 2556), (2556, 1179),
        (1290, 2796), (2796, 1290),
    }

    if (w, h) in common_screen_resolutions and not has_camera_exif:
        reason = f"Standard display resolution ({w}x{h}) without camera sensor EXIF tags."
        return "screenshot", reason, details

    # 4. social_media_reupload: JPEG quality < 75 or typical resized dims with stripped EXIF
    social_dims = {1080, 1200, 2048, 1440}
    is_social_dim = (w in social_dims or h in social_dims) and not has_camera_exif
    if (jpeg_q is not None and jpeg_q < 75) or is_social_dim:
        reason = (
            f"Heavily compressed re-upload (estimated JPEG quality {jpeg_q if jpeg_q else 'unknown'} < 75 "
            f"or social-media dimensions without camera metadata)."
        )
        return "social_media_reupload", reason, details

    # 5. camera_photo
    if has_camera_exif:
        camera_desc = f"{exif_tags.get('Make', '')} {exif_tags.get('Model', '')}".strip()
        reason = f"Camera EXIF tags present ({camera_desc or 'standard camera tags'})."
        return "camera_photo", reason, details

    # 6. ai_render (fallback)
    reason = "Synthetic rendering or digital illustration without physical camera artifacts."
    return "ai_render", reason, details


# ---------------------------------------------------------------------------
# Stage 8: Provenance & AI Marker Inspection
# ---------------------------------------------------------------------------
def check_provenance_markers(file_bytes: bytes, exif_tags: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scans metadata and binary buffer for known AI generator signatures and C2PA markers.
    Returns list of provenance findings.
    """
    findings = []
    lower_bytes = file_bytes.lower()

    # Generator markers to scan
    ai_signatures = [
        (b"midjourney", "Midjourney"),
        (b"dall-e", "DALL-E"),
        (b"stable diffusion", "Stable Diffusion"),
        (b"comfyui", "ComfyUI"),
        (b"automatic1111", "Automatic1111 WebUI"),
        (b"novelai", "NovelAI"),
        (b"adobe firefly", "Adobe Firefly"),
        (b"imagen", "Google Imagen"),
        (b"flux.1", "Black Forest Labs FLUX"),
        (b"bing image creator", "Bing Image Creator"),
    ]

    detected_generators = set()

    # Search raw bytes (covers PNG text chunks, XMP, JPEG APP segments)
    for sig_bytes, gen_name in ai_signatures:
        if sig_bytes in lower_bytes:
            detected_generators.add(gen_name)

    # Search EXIF string values
    for k, v in exif_tags.items():
        v_str = str(v).lower()
        for sig_bytes, gen_name in ai_signatures:
            if sig_bytes.decode("ascii") in v_str:
                detected_generators.add(gen_name)

    # C2PA / Content Credentials markers
    # TODO: Implement full C2PA manifest parsing and JUMBF box signature validation.
    c2pa_detected = (
        b"c2pa" in lower_bytes or
        b"jumbf" in lower_bytes or
        b"urn:c2pa:" in lower_bytes
    )

    if detected_generators:
        gens = ", ".join(sorted(detected_generators))
        findings.append({
            "id": "prov_ai_sig_01",
            "check": "provenance_AI_marker",
            "severity": "high",
            "confidence": 0.99,
            "description": f"Explicit AI generator metadata signature detected in file header/XMP: {gens}.",
            "location": {"metadata_field": "XMP/EXIF/Chunk"},
            "evidence_artifacts": []
        })

    if c2pa_detected:
        findings.append({
            "id": "prov_c2pa_01",
            "check": "provenance_AI_marker",
            "severity": "medium",
            "confidence": 0.90,
            "description": "Content Credentials (C2PA / JUMBF) assertion markers present in image structure.",
            "location": {"metadata_field": "C2PA_Manifest"},
            "evidence_artifacts": []
        })

    return findings


# ---------------------------------------------------------------------------
# Stage 5: Calibration (Platt Scaling)
# ---------------------------------------------------------------------------
def load_calibration_params() -> Tuple[float, float]:
    """Reads Platt scaling parameters (a, b) from configs/calibration.yaml."""
    if not CALIBRATION_PATH.is_file():
        return 1.0, 0.0

    try:
        with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        calib = data.get("calibration", {})
        return float(calib.get("a", 1.0)), float(calib.get("b", 0.0))
    except Exception:
        return 1.0, 0.0


def apply_platt_scaling(raw_score: float, a: float, b: float) -> float:
    """
    Calibrates raw probability via Platt scaling:
        logit = ln(s / (1 - s))
        P(fake) = 1 / (1 + exp(-(a * logit + b)))
    """
    eps = 1e-7
    s = min(max(raw_score, eps), 1.0 - eps)
    logit = math.log(s / (1.0 - s))
    calibrated = 1.0 / (1.0 + math.exp(-(a * logit + b)))
    return min(max(calibrated, 0.0), 1.0)


# ---------------------------------------------------------------------------
# Visual Artifact: Crop-Score Heatmap Generation
# ---------------------------------------------------------------------------
def render_crop_heatmap(
    img: Image.Image,
    crop_boxes: List[Tuple[int, int, int, int]],
    crop_scores: List[float],
    artifacts_dir: Path,
    sha256: str,
    th_fake: float = 0.80,
    th_real: float = 0.20
) -> str:
    """
    Overlays a 3x3 crop grid showing per-crop fake probability percentages on the image.
    Saves to artifacts_dir and returns relative path.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"{sha256[:16]}_heatmap.png"
    out_path = artifacts_dir / out_filename

    # Create RGBA overlay
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw crops
    for (x1, y1, x2, y2), score in zip(crop_boxes, crop_scores):
        if score >= th_fake:
            box_color = (239, 68, 68, 180)   # Red
            fill_color = (239, 68, 68, 45)
        elif score <= th_real:
            box_color = (16, 185, 129, 180) # Green
            fill_color = (16, 185, 129, 45)
        else:
            box_color = (245, 158, 11, 180) # Amber
            fill_color = (245, 158, 11, 45)

        # Draw box and fill
        draw.rectangle([x1, y1, x2, y2], outline=box_color, fill=fill_color, width=3)

        # Label pill
        lbl = f"{score * 100:.0f}%"
        px1, py1 = x1 + 6, y1 + 6
        px2, py2 = px1 + 48, py1 + 22
        draw.rounded_rectangle([px1, py1, px2, py2], radius=4, fill=(15, 23, 42, 220), outline=box_color, width=1)
        draw.text((px1 + 8, py1 + 4), lbl, fill=(255, 255, 255, 240))

    composite = Image.alpha_composite(base, overlay).convert("RGB")
    composite.save(out_path, format="PNG")

    return f"ai_image_detection/{out_filename}"


# ---------------------------------------------------------------------------
# Caching Helper
# ---------------------------------------------------------------------------
def get_cache_key(sha256: str) -> str:
    """Generates local cache key based on file hash + config modifications."""
    cfg_stat = ""
    if THRESHOLDS_PATH.is_file():
        cfg_stat += str(THRESHOLDS_PATH.stat().st_mtime)
    if CALIBRATION_PATH.is_file():
        cfg_stat += str(CALIBRATION_PATH.stat().st_mtime)
    combined = f"{sha256}_{cfg_stat}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Helper for calibration script
# ---------------------------------------------------------------------------
def compute_raw_score_for_file(file_path_str: str) -> Tuple[float, Optional[str]]:
    """Helper used by calibrate.py to extract raw average crop score."""
    p = Path(file_path_str)
    img, info, err = ingest_image(p)
    if err or img is None:
        return 0.0, err or "Ingestion failed"

    crops, _, _ = generate_crops(img)
    mgr = ModelManager.get_instance()
    success, load_err = mgr.load_models()
    if not success:
        return 0.0, load_err

    tensors = [preprocess_crop_to_tensor(c) for c in crops]
    batch = torch.stack(tensors).to(mgr.device)

    with torch.no_grad():
        features = mgr.clip_model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)
        if mgr.use_fp16:
            features = features.float()
        logits = mgr.linear_probe(features)
        crop_scores = torch.sigmoid(logits).squeeze(-1).cpu().numpy().tolist()

    if isinstance(crop_scores, float):
        crop_scores = [crop_scores]

    return float(np.mean(crop_scores)), None


# ---------------------------------------------------------------------------
# CORE ENTRY POINT (Contract Requirement)
# ---------------------------------------------------------------------------
def analyze(file_path: str, options: dict | None = None) -> dict:
    """
    Main forensic entry point for ai_image_detection.
    Signature required by Integration Contract:
        def analyze(file_path: str, options: dict | None = None) -> dict
    Never raises exceptions to caller; returns standard result format.
    """
    start_time = time.perf_counter()
    p = Path(file_path)
    options = options or {}

    # Destination directories
    env_artifact_dir = os.environ.get("ARTIFACT_DIR")
    if env_artifact_dir:
        artifacts_root = Path(env_artifact_dir)
    else:
        artifacts_root = MODULE_DIR.parent / "artifacts"
    module_artifacts_dir = artifacts_root / "ai_image_detection"

    analyzed_at = datetime.now(timezone.utc).isoformat()
    errors: List[str] = []
    findings: List[Dict[str, Any]] = []

    # Evidence File Record
    evidence_file = {
        "name": p.name if p.exists() else "unknown",
        "sha256": "",
        "size_bytes": 0,
        "type": "unknown",
    }

    raw_metrics: Dict[str, Any] = {
        "module_version": "1.0",
        "clip_checkpoint": "ViT-L/14",
        "device": "cpu",
        "inference_ms": 0.0,
        "model_loaded": False
    }

    # 1. Chain-of-Custody SHA-256 calculation & File Ingestion
    if not p.is_file():
        errors.append(f"Evidence file not found: {file_path}")
        return {
            "module": "ai_image_detection",
            "version": "1.0",
            "evidence_file": evidence_file,
            "analyzed_at": analyzed_at,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": findings,
            "artifacts_dir": "artifacts/ai_image_detection",
            "errors": errors,
            "raw_metrics": raw_metrics,
        }

    try:
        sha256 = compute_sha256(p)
        evidence_file["sha256"] = sha256
        evidence_file["size_bytes"] = p.stat().st_size
    except Exception as e:
        errors.append(f"Failed to read file buffer for SHA-256: {str(e)}")
        return {
            "module": "ai_image_detection",
            "version": "1.0",
            "evidence_file": evidence_file,
            "analyzed_at": analyzed_at,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": findings,
            "artifacts_dir": "artifacts/ai_image_detection",
            "errors": errors,
            "raw_metrics": raw_metrics,
        }

    # Check local cache (instant re-analysis)
    cache_key = get_cache_key(sha256)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.is_file() and not options.get("no_cache", False):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                cached_res = json.load(cf)
                cached_res["analyzed_at"] = analyzed_at
                cached_res["raw_metrics"]["cache_hit"] = True
                return cached_res
        except Exception:
            pass

    # Read binary bytes for header inspection & provenance
    try:
        with open(p, "rb") as f:
            file_bytes = f.read()
    except Exception as e:
        errors.append(f"Failed to read file bytes: {str(e)}")
        file_bytes = b""

    # Ingest image with Pillow
    img, info, ingest_err = ingest_image(p)
    if ingest_err:
        errors.append(ingest_err)
        return {
            "module": "ai_image_detection",
            "version": "1.0",
            "evidence_file": evidence_file,
            "analyzed_at": analyzed_at,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": findings,
            "artifacts_dir": "artifacts/ai_image_detection",
            "errors": errors,
            "raw_metrics": raw_metrics,
        }

    evidence_file["type"] = f"image/{info['format'].lower()}"
    raw_metrics["jpeg_quality_estimate"] = info.get("jpeg_quality")
    raw_metrics["image_dimensions"] = [info["width"], info["height"]]

    # Extract EXIF tags
    exif_tags = {}
    try:
        raw_exif = img.getexif()
        if raw_exif:
            for k, v in raw_exif.items():
                exif_tags[Image.ExifTags.TAGS.get(k, str(k))] = str(v)
    except Exception:
        pass

    # Stage 6: Photo-Type Detection Heuristics
    photo_type, pt_reason, pt_details = detect_photo_type(img, info, file_bytes, exif_tags)
    raw_metrics["photo_type"] = photo_type
    raw_metrics["photo_type_details"] = pt_details

    # Stage 8: Provenance & AI Marker Inspection
    provenance_findings = check_provenance_markers(file_bytes, exif_tags)

    # Multi-Crop Preparation (Stage 2)
    crops, crop_boxes, is_padded = generate_crops(img)
    raw_metrics["num_crops"] = len(crops)
    raw_metrics["is_padded"] = is_padded

    if is_padded:
        findings.append({
            "id": "chk_img_too_small",
            "check": "image_too_small",
            "severity": "medium",
            "confidence": 0.85,
            "description": (
                f"Image resolution ({info['width']}x{info['height']}) is smaller than the model receptive "
                f"field (224x224). Reflection/border padding was applied, which may influence high-frequency forensic metrics."
            ),
            "location": {"region": [0, 0, info["width"], info["height"]]},
            "evidence_artifacts": []
        })

    # Model Manager & Feature Extraction (Stages 3 & 4)
    mgr = ModelManager.get_instance()
    raw_metrics["device"] = mgr.device
    models_ready, load_err = mgr.load_models()

    raw_score = 0.5
    calibrated_prob = 0.5
    crop_scores = [0.5] * len(crops)

    if not models_ready:
        errors.append(load_err or "Model weights unavailable.")
    else:
        raw_metrics["model_loaded"] = True
        try:
            tensors = [preprocess_crop_to_tensor(c) for c in crops]
            batch = torch.stack(tensors).to(mgr.device)

            with torch.no_grad():
                features = mgr.clip_model.encode_image(batch)
                features = features / features.norm(dim=-1, keepdim=True)
                if mgr.use_fp16:
                    features = features.float()
                logits = mgr.linear_probe(features)
                scores_tensor = torch.sigmoid(logits).squeeze(-1)
                crop_scores = scores_tensor.cpu().numpy().tolist()
                if isinstance(crop_scores, float):
                    crop_scores = [crop_scores]

            raw_score = float(np.mean(crop_scores))

            # Stage 5: Platt Scaling Calibration
            calib_a, calib_b = load_calibration_params()
            raw_metrics["calibration_params"] = {"a": calib_a, "b": calib_b}
            calibrated_prob = apply_platt_scaling(raw_score, calib_a, calib_b)

        except Exception as e:
            if "cuda" in str(mgr.device).lower():
                try:
                    logger.warning("CUDA execution failed, falling back to CPU: %s", e)
                    mgr.device = "cpu"
                    mgr.use_fp16 = False
                    if mgr.clip_model is not None:
                        mgr.clip_model = mgr.clip_model.to("cpu").float()
                    if mgr.linear_probe is not None:
                        mgr.linear_probe = mgr.linear_probe.to("cpu").float()
                    batch_cpu = torch.stack(tensors).to("cpu")
                    with torch.no_grad():
                        features = mgr.clip_model.encode_image(batch_cpu)
                        features = features / features.norm(dim=-1, keepdim=True)
                        logits = mgr.linear_probe(features.float())
                        scores_tensor = torch.sigmoid(logits).squeeze(-1)
                        crop_scores = scores_tensor.cpu().numpy().tolist()
                        if isinstance(crop_scores, float):
                            crop_scores = [crop_scores]
                    raw_score = float(np.mean(crop_scores))
                    calib_a, calib_b = load_calibration_params()
                    raw_metrics["calibration_params"] = {"a": calib_a, "b": calib_b}
                    calibrated_prob = apply_platt_scaling(raw_score, calib_a, calib_b)
                    raw_metrics["device"] = "cpu (fallback)"
                except Exception as e2:
                    errors.append(f"Inference execution failed on CPU fallback: {str(e2)}")
            else:
                errors.append(f"Inference execution failed: {str(e)}")

    crop_scores = [round(float(s), 4) for s in crop_scores]
    raw_metrics["raw_score"] = round(raw_score, 4)
    raw_metrics["calibrated_probability"] = round(calibrated_prob, 4)
    raw_metrics["per_crop_scores"] = crop_scores

    # Stage 7: Decision Logic & Thresholds
    thresholds = load_thresholds()
    raw_metrics["thresholds_used"] = thresholds.get(photo_type, thresholds.get("camera_photo"))

    verdict, decision_label, overall_conf, decision_desc, th_info = evaluate_decision(
        photo_type, calibrated_prob, thresholds
    )

    # Generate Visual Artifact (Crop Heatmap)
    heatmap_rel_path = render_crop_heatmap(
        img,
        crop_boxes,
        crop_scores,
        module_artifacts_dir,
        sha256,
        th_fake=th_info.get("fake_threshold") or 0.80,
        th_real=th_info.get("real_threshold") or 0.20
    )

    # Construct Findings
    # Finding 1: UnivFD AI Fake Probability
    fake_pct = calibrated_prob * 100.0
    sev = "high" if verdict == "likely_tampered" else ("medium" if verdict == "suspicious" else "low")
    findings.append({
        "id": "chk_univfd_fake_prob",
        "check": "UnivFD_fake_probability",
        "severity": sev,
        "confidence": overall_conf,
        "description": f"UnivFD CLIP linear probe yields calibrated fake probability of {fake_pct:.1f}%. {decision_desc}",
        "location": {"region": [0, 0, info["width"], info["height"]]},
        "evidence_artifacts": [heatmap_rel_path]
    })

    # Finding 2: Photo Type and Quality
    findings.append({
        "id": "chk_photo_type_quality",
        "check": "photo_type_and_quality",
        "severity": "info" if photo_type == "camera_photo" else "low",
        "confidence": 0.85,
        "description": f"Image categorized as '{photo_type.replace('_', ' ')}': {pt_reason}",
        "location": {"region": [0, 0, info["width"], info["height"]]},
        "evidence_artifacts": []
    })

    # Finding 3: Multi-Crop Consistency
    if len(crop_scores) > 1:
        score_std = float(np.std(crop_scores))
        raw_metrics["crop_score_std"] = round(score_std, 4)
        if score_std > 0.20:
            findings.append({
                "id": "chk_crop_consistency",
                "check": "multi_crop_consistency",
                "severity": "medium",
                "confidence": 0.75,
                "description": (
                    f"Noticeable divergence across 3x3 crop regions (std dev {score_std:.2f}). "
                    f"This may indicate localized AI inpainting, splicing, or face-swapping."
                ),
                "location": {"region": [0, 0, info["width"], info["height"]]},
                "evidence_artifacts": [heatmap_rel_path]
            })

    # Prepend Provenance Findings (FIRST as specified in contract)
    if provenance_findings:
        findings = provenance_findings + findings
        # Provenance overrides the classifier:
        verdict = "likely_tampered"
        overall_conf = 0.98

    # Standing Finding (Required by Contract)
    findings.append({
        "id": "chk_standing_disclaimer",
        "check": "standing_disclaimer",
        "severity": "info",
        "confidence": 1.0,
        "description": (
            "This score is evidence, not proof. It can miss partial AI edits and newer generators. "
            "Corroborate with metadata, ELA, and provenance checks."
        ),
        "location": None,
        "evidence_artifacts": []
    })

    # Sort findings by severity (high > medium > low > info)
    sev_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: sev_order.get(f["severity"], 4))

    raw_metrics["inference_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)

    # Standard Result Format
    result = {
        "module": "ai_image_detection",
        "version": "1.0",
        "evidence_file": evidence_file,
        "analyzed_at": analyzed_at,
        "verdict": verdict,
        "overall_confidence": overall_conf,
        "findings": findings,
        "artifacts_dir": "artifacts/ai_image_detection",
        "errors": errors,
        "raw_metrics": raw_metrics,
    }

    # Save to local cache
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as cf:
            json.dump(result, cf, indent=2)
    except Exception:
        pass

    return result
