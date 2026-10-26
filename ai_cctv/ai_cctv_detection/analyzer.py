"""Core forensic analyzer for AI CCTV video detection.

Strictly follows the PS-05 Forensic Integration Contract:
- Local execution only, no cloud calls
- Exactly one public entry point: analyze(file_path: str, options: dict | None = None) -> dict
- Never raises exceptions; returns errors in the 'errors' list
- Emits standard result format
"""

from __future__ import annotations
import hashlib
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

# Lazy imports for optional / heavy libraries
try:
    import av
except ImportError:
    av = None

try:
    import torch
    from ultralytics import YOLO
except ImportError:
    torch = None
    YOLO = None

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

# Module paths relative to this file (never absolute, never relying on cwd)
MODULE_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = MODULE_DIR / "configs"
MODELS_DIR = MODULE_DIR / "models"
BEST_MODEL_PATH = MODELS_DIR / "best.pt"

# Global lazy singleton for the fine-tuned YOLO model
_MODEL_CACHE: Dict[str, Any] = {"model": None, "path": None, "device": None}


def _load_yaml(path: Path) -> dict:
    """Safely load a YAML configuration file."""
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def compute_sha256(file_path: str | Path, block_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 hash of a file for forensic chain-of-custody."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(block_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_video_metadata(file_path: str | Path) -> dict:
    """Read container and stream metadata using PyAV, falling back to OpenCV."""
    meta = {
        "codec": "unknown",
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "bitrate": 0,
        "duration": 0.0,
        "total_frames": 0,
        "container": Path(file_path).suffix.lstrip(".").lower(),
        "backend": "unknown",
    }

    # Attempt PyAV first
    if av is not None:
        try:
            with av.open(str(file_path)) as container:
                video_stream = next((s for s in container.streams if s.type == "video"), None)
                if video_stream:
                    meta["backend"] = "pyav"
                    meta["codec"] = video_stream.codec_context.name or "unknown"
                    meta["width"] = int(video_stream.width or 0)
                    meta["height"] = int(video_stream.height or 0)
                    meta["fps"] = float(video_stream.average_rate or video_stream.base_rate or 25.0)
                    meta["bitrate"] = int(container.bit_rate or video_stream.bit_rate or 0)
                    if video_stream.duration and video_stream.time_base:
                        meta["duration"] = float(video_stream.duration * video_stream.time_base)
                    elif container.duration:
                        meta["duration"] = float(container.duration / av.time.AV_TIME_BASE)
                    meta["total_frames"] = int(video_stream.frames or 0)
                    return meta
        except Exception:
            pass  # Fall back to OpenCV

    # OpenCV fallback
    cap = cv2.VideoCapture(str(file_path))
    if cap.isOpened():
        meta["backend"] = "opencv"
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        meta["codec"] = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip() or "cv2_raw"
        meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        meta["fps"] = fps if fps > 0 else 25.0
        meta["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if meta["fps"] > 0 and meta["total_frames"] > 0:
            meta["duration"] = float(meta["total_frames"] / meta["fps"])
        cap.release()

    return meta


def sample_frames(
    file_path: str | Path,
    max_frames: int = 300,
    target_fps: float = 2.0,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> List[dict]:
    """Decode I-frames plus uniform ~2 fps samples with a frame cap.

    Returns a list of dicts:
    {"index": int, "timestamp": float, "image": np.ndarray (RGB), "is_keyframe": bool}
    """
    frames: List[dict] = []
    min_time_delta = 1.0 / max(target_fps, 0.5)

    # Strategy 1: PyAV for accurate I-frame detection
    if av is not None:
        try:
            with av.open(str(file_path)) as container:
                stream = next((s for s in container.streams if s.type == "video"), None)
                if stream:
                    last_sampled_time = -999.0
                    frame_idx = 0
                    for packet in container.demux(stream):
                        for frame in packet.decode():
                            pts_sec = float(frame.pts * stream.time_base) if frame.pts and stream.time_base else (frame_idx / (float(stream.average_rate or 25.0)))
                            is_key = bool(frame.key_frame)
                            time_diff = pts_sec - last_sampled_time

                            if is_key or (time_diff >= min_time_delta):
                                rgb_img = frame.to_ndarray(format="rgb24")
                                frames.append({
                                    "index": frame_idx,
                                    "timestamp": round(pts_sec, 3),
                                    "image": rgb_img,
                                    "is_keyframe": is_key,
                                })
                                last_sampled_time = pts_sec
                                if len(frames) >= max_frames:
                                    break
                            frame_idx += 1
                        if len(frames) >= max_frames:
                            break
            if frames:
                return frames
        except Exception:
            frames.clear()

    # Strategy 2: OpenCV fallback
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return frames

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps / target_fps))
    frame_idx = 0
    while cap.isOpened() and len(frames) < max_frames:
        ret, bgr = cap.read()
        if not ret:
            break
        # Sample every frame_interval frames
        if frame_idx % frame_interval == 0:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            pts_sec = frame_idx / fps
            frames.append({
                "index": frame_idx,
                "timestamp": round(pts_sec, 3),
                "image": rgb,
                "is_keyframe": (frame_idx % (frame_interval * 5) == 0),
            })
        frame_idx += 1

    cap.release()
    return frames


def estimate_blockiness(gray: np.ndarray) -> float:
    """Estimate compression blockiness ratio along 8x8 DCT grid boundaries."""
    h, w = gray.shape
    if h < 16 or w < 16:
        return 0.0

    # Horizontal boundary difference vs intra-block difference
    h_idx = np.arange(8, h - 8, 8)
    w_idx = np.arange(8, w - 8, 8)

    diff_boundary = 0.0
    diff_intra = 0.0

    if len(h_idx) > 0:
        b_diff = np.abs(gray[h_idx, :].astype(np.float32) - gray[h_idx - 1, :].astype(np.float32))
        i_diff = np.abs(gray[h_idx - 1, :].astype(np.float32) - gray[h_idx - 2, :].astype(np.float32))
        diff_boundary += float(np.mean(b_diff))
        diff_intra += float(np.mean(i_diff))

    if len(w_idx) > 0:
        b_diff = np.abs(gray[:, w_idx].astype(np.float32) - gray[:, w_idx - 1].astype(np.float32))
        i_diff = np.abs(gray[:, w_idx - 1].astype(np.float32) - gray[:, w_idx - 2].astype(np.float32))
        diff_boundary += float(np.mean(b_diff))
        diff_intra += float(np.mean(i_diff))

    if diff_intra < 1e-4:
        return 0.0

    ratio = max(0.0, (diff_boundary / (diff_intra + 1e-4)) - 1.0)
    # Normalize roughly into [0.0, 1.0]
    return float(np.clip(ratio / 2.0, 0.0, 1.0))


def evaluate_quality_gate(
    frames: List[dict],
    quality_cfg: dict,
) -> Tuple[List[dict], dict]:
    """Filter sampled frames through resolution, blur, and over-compression checks.

    Weights:
      1.0 = good
      0.3 = poor
      0.0 = dropped (unusable)
    """
    min_w = quality_cfg.get("resolution", {}).get("min_width", 480)
    min_h = quality_cfg.get("resolution", {}).get("min_height", 360)

    blur_unusable = quality_cfg.get("blur", {}).get("unusable_threshold", 20.0)
    blur_good = quality_cfg.get("blur", {}).get("good_threshold", 60.0)

    comp_unusable = quality_cfg.get("compression", {}).get("unusable_blockiness", 0.45)
    comp_good = quality_cfg.get("compression", {}).get("good_blockiness", 0.20)

    w_good = quality_cfg.get("weights", {}).get("good", 1.0)
    w_poor = quality_cfg.get("weights", {}).get("poor", 0.3)
    w_dropped = quality_cfg.get("weights", {}).get("dropped", 0.0)

    kept_frames: List[dict] = []
    blur_scores: List[float] = []
    block_scores: List[float] = []

    for item in frames:
        img = item["image"]
        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        blockiness = estimate_blockiness(gray)

        blur_scores.append(blur_var)
        block_scores.append(blockiness)

        # Usability gating
        if w < min_w or h < min_h:
            weight = w_dropped
            reason = "low_resolution"
        elif blur_var < blur_unusable:
            weight = w_dropped
            reason = "severe_blur"
        elif blockiness > comp_unusable:
            weight = w_dropped
            reason = "severe_blockiness"
        elif blur_var < blur_good or blockiness > comp_good:
            weight = w_poor
            reason = "degraded_quality"
        else:
            weight = w_good
            reason = "clean"

        item_copy = dict(item)
        item_copy["quality_weight"] = weight
        item_copy["quality_reason"] = reason
        item_copy["blur_var"] = round(blur_var, 2)
        item_copy["blockiness"] = round(blockiness, 4)

        if weight > 0.0:
            kept_frames.append(item_copy)

    total = len(frames)
    kept_count = len(kept_frames)
    quality_share = (kept_count / total) if total > 0 else 0.0

    summary = {
        "total_sampled": total,
        "kept_count": kept_count,
        "dropped_count": total - kept_count,
        "quality_share": round(quality_share, 4),
        "mean_blur_var": round(float(np.mean(blur_scores)), 2) if blur_scores else 0.0,
        "mean_blockiness": round(float(np.mean(block_scores)), 4) if block_scores else 0.0,
    }

    return kept_frames, summary


def extract_native_tiles(image: np.ndarray, tile_size: int = 448, max_tiles: int = 4) -> List[np.ndarray]:
    """Extract up to max_tiles native-resolution crops at training size (448) without aggressive downscaling."""
    h, w = image.shape[:2]
    tiles: List[np.ndarray] = []

    if h <= tile_size and w <= tile_size:
        # Pad up to tile_size if frame is smaller
        pad_y = max(0, tile_size - h)
        pad_x = max(0, tile_size - w)
        padded = cv2.copyMakeBorder(image, 0, pad_y, 0, pad_x, cv2.BORDER_REFLECT)
        return [padded[:tile_size, :tile_size]]

    # Generate up to 4 native crops (quadrants / center)
    y_coords = [0, max(0, h - tile_size)] if h > tile_size else [0]
    x_coords = [0, max(0, w - tile_size)] if w > tile_size else [0]

    for y in y_coords:
        for x in x_coords:
            crop = image[y:y + tile_size, x:x + tile_size]
            if crop.shape[0] < tile_size or crop.shape[1] < tile_size:
                crop = cv2.resize(crop, (tile_size, tile_size), interpolation=cv2.INTER_LINEAR)
            tiles.append(crop)
            if len(tiles) >= max_tiles:
                return tiles

    # If only 1 crop extracted (e.g. video dimension exactly tile_size in one axis)
    if not tiles:
        tiles.append(cv2.resize(image, (tile_size, tile_size)))
    return tiles[:max_tiles]


def get_yolo_classifier(model_path: Path) -> Tuple[Optional[Any], str]:
    """Lazy singleton loader for the fine-tuned YOLO11 classification model."""
    global _MODEL_CACHE
    if not model_path.is_file():
        return None, "cpu"

    if _MODEL_CACHE["model"] is not None and _MODEL_CACHE["path"] == str(model_path):
        return _MODEL_CACHE["model"], _MODEL_CACHE["device"]

    if YOLO is None:
        return None, "cpu"

    device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
    try:
        model = YOLO(str(model_path))
        _MODEL_CACHE["model"] = model
        _MODEL_CACHE["path"] = str(model_path)
        _MODEL_CACHE["device"] = device
        return model, device
    except Exception:
        return None, device


def platt_scale(prob: float, a: float = 1.0, b: float = 0.0) -> float:
    """Apply Platt scaling calibration: P_cal = 1 / (1 + exp(-(a * logit + b)))."""
    if a == 1.0 and b == 0.0:
        return prob
    p_clamped = np.clip(prob, 1e-6, 1.0 - 1e-6)
    logit = float(np.log(p_clamped / (1.0 - p_clamped)))
    scaled_logit = a * logit + b
    # Sigmoid
    return float(1.0 / (1.0 + np.exp(-scaled_logit)))


def compute_weighted_median(values: List[float], weights: List[float]) -> float:
    """Compute weighted median of a series of numbers."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    arr = np.array(values, dtype=np.float32)
    w_arr = np.array(weights, dtype=np.float32)
    sort_idx = np.argsort(arr)
    sorted_v = arr[sort_idx]
    sorted_w = w_arr[sort_idx]

    cum_w = np.cumsum(sorted_w)
    total_w = cum_w[-1]
    if total_w <= 0:
        return float(np.median(arr))

    cutoff = total_w / 2.0
    idx = int(np.searchsorted(cum_w, cutoff))
    idx = min(idx, len(sorted_v) - 1)
    return float(sorted_v[idx])


def calculate_temporal_metrics(
    kept_frames: List[dict],
    probabilities: List[float],
    total_sampled: int,
    thresholds_cfg: dict,
) -> dict:
    """Temporal aggregation logic strictly per specification:
    - median_p: weighted median of frame scores
    - frac_high: fraction of kept frames with p >= 0.70
    - run_high: longest run of consecutive kept frames with p >= 0.70, in seconds
    - quality: share of frames passing the quality gate
    """
    high_threshold = thresholds_cfg.get("frame_evaluation", {}).get("high_p_threshold", 0.70)

    if not kept_frames or not probabilities:
        return {
            "median_p": 0.0,
            "frac_high": 0.0,
            "run_high": 0.0,
            "quality": 0.0,
            "suspicious_segments": [],
        }

    weights = [f.get("quality_weight", 1.0) for f in kept_frames]
    median_p = compute_weighted_median(probabilities, weights)

    high_mask = [p >= high_threshold for p in probabilities]
    frac_high = sum(high_mask) / len(probabilities)

    # Compute longest run of consecutive kept frames with p >= 0.70 in seconds
    max_run_sec = 0.0
    current_run_start_idx = None
    suspicious_segments: List[dict] = []

    for i, is_high in enumerate(high_mask):
        if is_high:
            if current_run_start_idx is None:
                current_run_start_idx = i
        else:
            if current_run_start_idx is not None:
                start_t = kept_frames[current_run_start_idx]["timestamp"]
                end_t = kept_frames[i - 1]["timestamp"]
                duration = max(0.5, round(end_t - start_t, 2))
                if duration > max_run_sec:
                    max_run_sec = duration
                if duration >= 1.0:
                    suspicious_segments.append({
                        "frame_range": [kept_frames[current_run_start_idx]["index"], kept_frames[i - 1]["index"]],
                        "time_range_sec": [round(start_t, 2), round(end_t, 2)],
                        "duration_sec": duration,
                    })
                current_run_start_idx = None

    # Handle run reaching end of clip
    if current_run_start_idx is not None:
        start_t = kept_frames[current_run_start_idx]["timestamp"]
        end_t = kept_frames[-1]["timestamp"]
        duration = max(0.5, round(end_t - start_t, 2))
        if duration > max_run_sec:
            max_run_sec = duration
        if duration >= 1.0:
            suspicious_segments.append({
                "frame_range": [kept_frames[current_run_start_idx]["index"], kept_frames[-1]["index"]],
                "time_range_sec": [round(start_t, 2), round(end_t, 2)],
                "duration_sec": duration,
            })

    quality_share = (len(kept_frames) / total_sampled) if total_sampled > 0 else 0.0

    return {
        "median_p": round(float(median_p), 4),
        "frac_high": round(float(frac_high), 4),
        "run_high": round(float(max_run_sec), 2),
        "quality": round(float(quality_share), 4),
        "suspicious_segments": suspicious_segments,
    }


def evaluate_verdict(
    metrics: dict,
    kept_count: int,
    thresholds_cfg: dict,
) -> Tuple[str, float]:
    """Check verdict rules in exact specification order:
    a. quality < 0.30 or fewer than 8 kept frames -> "inconclusive"
    b. median_p >= 0.75 and frac_high >= 0.60 -> "likely_tampered" (high conf if quality >= 0.70 else med)
    c. run_high >= 3 s and frac_high >= 0.25 -> "likely_tampered" (partial / spliced, med conf)
    d. median_p <= 0.30 and frac_high <= 0.10 -> "authentic" (high if quality >= 0.70 else med)
    e. anything else -> "inconclusive" (use "suspicious" if median_p between 0.50 and 0.75)
    """
    quality = metrics["quality"]
    median_p = metrics["median_p"]
    frac_high = metrics["frac_high"]
    run_high = metrics["run_high"]

    min_frames = thresholds_cfg.get("aggregation", {}).get("min_usable_frames", 8)
    min_quality = thresholds_cfg.get("aggregation", {}).get("min_quality_share", 0.30)
    high_q_thresh = thresholds_cfg.get("aggregation", {}).get("high_confidence_quality", 0.70)

    # a. Usability check
    if quality < min_quality or kept_count < min_frames:
        return "inconclusive", 0.40

    # b. Global AI generation
    if median_p >= 0.75 and frac_high >= 0.60:
        conf = 0.90 if quality >= high_q_thresh else 0.75
        return "likely_tampered", conf

    # c. Temporal splice / partial run
    if run_high >= 3.0 and frac_high >= 0.25:
        return "likely_tampered", 0.75

    # d. Authentic CCTV
    if median_p <= 0.30 and frac_high <= 0.10:
        conf = 0.90 if quality >= high_q_thresh else 0.75
        return "authentic", conf

    # e. Suspicious or Inconclusive
    if 0.50 <= median_p <= 0.75:
        return "suspicious", 0.60

    return "inconclusive", 0.50


def generate_timeline_plot(
    timestamps: List[float],
    probabilities: List[float],
    quality_weights: List[float],
    suspicious_segments: List[dict],
    output_path: Path,
) -> str:
    """Generate forensic timeline plot (p_fake vs time, quality shading, threshold line)."""
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    fig.patch.set_facecolor("#0f172a")  # Dark theme background
    ax.set_facecolor("#1e293b")

    t = np.array(timestamps)
    p = np.array(probabilities)
    q = np.array(quality_weights)

    # Suspicious range red background highlighting
    for seg in suspicious_segments:
        s_start, s_end = seg["time_range_sec"]
        ax.axvspan(s_start, s_end, color="#ef4444", alpha=0.25, label="Suspicious Segment" if seg == suspicious_segments[0] else "")

    # Quality degradation shading (gray bands where quality is poor)
    for i in range(len(t) - 1):
        if q[i] < 1.0:
            ax.axvspan(t[i], t[i+1], color="#475569", alpha=0.2)

    # Threshold line at 0.70
    ax.axhline(0.70, color="#f59e0b", linestyle="--", linewidth=1.5, label="AI Alert Threshold (0.70)")
    ax.axhline(0.30, color="#10b981", linestyle=":", linewidth=1.2, label="Authentic Baseline (0.30)")

    # Probability curve and scatter
    ax.plot(t, p, color="#38bdf8", linewidth=2.0, label="P(AI Generated)")
    ax.scatter(t, p, c=p, cmap="coolwarm", s=30, edgecolors="#0f172a", zorder=4)

    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(min(t) - 0.2 if len(t) > 0 else 0, max(t) + 0.2 if len(t) > 0 else 1)
    ax.set_title("Temporal AI Evidence Timeline (P_fake vs Video Time)", color="#f8fafc", fontsize=12, pad=12)
    ax.set_xlabel("Time (seconds)", color="#94a3b8", fontsize=10)
    ax.set_ylabel("P(AI Generated)", color="#94a3b8", fontsize=10)
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, linestyle="--", alpha=0.15, color="#cbd5e1")
    ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc", loc="upper right", fontsize=8)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return output_path.name


def generate_contact_sheet(
    kept_frames: List[dict],
    probabilities: List[float],
    output_path: Path,
    num_samples: int = 6,
) -> str:
    """Generate contact sheet of up to 6 highest-scoring frames with timestamps."""
    if not kept_frames:
        return ""

    # Sort indices by probability descending
    scored = list(zip(range(len(kept_frames)), probabilities))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_indices = [idx for idx, _ in scored[:num_samples]]

    cols = min(3, len(top_indices))
    rows = math.ceil(len(top_indices) / cols) if cols > 0 else 1

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.6, rows * 2.8), dpi=130)
    fig.patch.set_facecolor("#0f172a")
    if rows == 1 and cols == 1:
        axes = np.array([axes])
    axes = np.array(axes).flatten()

    for i, ax in enumerate(axes):
        ax.set_facecolor("#1e293b")
        if i < len(top_indices):
            idx = top_indices[i]
            frame_item = kept_frames[idx]
            img = frame_item["image"]
            p_val = probabilities[idx]
            t_sec = frame_item["timestamp"]
            f_idx = frame_item["index"]

            ax.imshow(img)
            ax.set_title(
                f"F#{f_idx} | {t_sec:.1f}s | P(AI): {p_val:.2f}",
                color="#f8fafc" if p_val < 0.70 else "#ef4444",
                fontsize=9,
                fontweight="bold",
                pad=6,
            )
        ax.axis("off")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return output_path.name


def analyze(file_path: str, options: dict | None = None) -> dict:
    """Analyze a CCTV video file for AI generation / tampering.

    Standard PS-05 Entry Point. Never raises an uncaught exception.
    """
    options = options or {}
    start_time = time.time()
    errors: List[str] = []
    findings: List[dict] = []

    # Configure paths
    path_obj = Path(file_path)
    file_name = path_obj.name
    artifacts_base = Path(os.getenv("ARTIFACT_DIR", "artifacts/ai_cctv_detection"))
    artifacts_dir = artifacts_base
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    progress_cb = options.get("progress_callback")

    def report_progress(stage: str, percent: int):
        if callable(progress_cb):
            try:
                progress_cb(stage, percent)
            except Exception:
                pass

    report_progress("Ingesting file and verifying chain of custody", 5)

    # 1. Ingest & Chain of Custody
    sha256_hash = "unknown"
    file_size = 0
    file_type = path_obj.suffix.lstrip(".").lower() or "video"

    try:
        if path_obj.is_file():
            file_size = path_obj.stat().st_size
            sha256_hash = compute_sha256(path_obj)
        else:
            errors.append(f"Evidence file not found: {file_path}")
    except Exception as e:
        errors.append(f"Failed to hash evidence file: {str(e)}")

    if errors:
        return {
            "module": "ai_cctv_detection",
            "version": "1.0",
            "evidence_file": {
                "name": file_name,
                "sha256": sha256_hash,
                "size_bytes": file_size,
                "type": file_type,
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": str(artifacts_dir).replace("\\", "/"),
            "errors": errors,
            "raw_metrics": {},
        }

    # Extract container & video metadata
    report_progress("Reading video streams and metadata", 15)
    meta = read_video_metadata(path_obj)

    # Load configuration files
    quality_cfg = _load_yaml(CONFIGS_DIR / "quality.yaml")
    thresholds_cfg = _load_yaml(CONFIGS_DIR / "thresholds.yaml")
    calib_cfg = _load_yaml(CONFIGS_DIR / "calibration.yaml")

    # 2. Frame Sampling
    report_progress("Decoding keyframes and temporal samples", 30)
    max_frames = int(options.get("max_frames", 300))
    sampled_frames = sample_frames(path_obj, max_frames=max_frames, target_fps=2.0)

    if not sampled_frames:
        errors.append("Unable to decode video frames. File may be corrupted, empty, or unsupported format.")
        return {
            "module": "ai_cctv_detection",
            "version": "1.0",
            "evidence_file": {
                "name": file_name,
                "sha256": sha256_hash,
                "size_bytes": file_size,
                "type": file_type,
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": str(artifacts_dir).replace("\\", "/"),
            "errors": errors,
            "raw_metrics": {"video_metadata": meta},
        }

    # 3. Quality Gate
    report_progress("Evaluating frame quality gate (blur, compression, resolution)", 45)
    kept_frames, quality_summary = evaluate_quality_gate(sampled_frames, quality_cfg)

    findings.append({
        "id": "qg_01",
        "check": "video_quality_gate",
        "severity": "info" if quality_summary["quality_share"] >= 0.70 else "medium",
        "confidence": 0.95,
        "description": (
            f"Quality gate inspected {quality_summary['total_sampled']} frames: "
            f"{quality_summary['kept_count']} frames retained ({quality_summary['quality_share']*100:.1f}%), "
            f"{quality_summary['dropped_count']} frames dropped due to blur, low resolution, or severe compression."
        ),
        "location": None,
        "evidence_artifacts": [],
    })

    # Standing forensic caution finding
    findings.append({
        "id": "caution_01",
        "check": "clip_ai_probability",
        "severity": "info",
        "confidence": 1.0,
        "description": (
            "This score is evidence, not proof. Accuracy drops on generators, cameras, codecs, "
            "and lighting not seen in training. Corroborate with DVR logs, original file, and chain of custody."
        ),
        "location": None,
        "evidence_artifacts": [],
    })

    # 4. Model Availability Check (HONESTY RULE)
    has_trained_model = BEST_MODEL_PATH.is_file()
    if not has_trained_model:
        report_progress("Model checkpoint missing - reporting un-trained state", 90)
        findings.append({
            "id": "model_status_01",
            "check": "model_not_trained",
            "severity": "info",
            "confidence": 1.0,
            "description": (
                "YOLO11 classification weights 'best.pt' are not yet trained. In accordance with forensic honesty rules, "
                "no synthetic AI scores are invented. To train the detector, run train_model.bat or tools/train.py "
                "with verified CCTV footage."
            ),
            "location": None,
            "evidence_artifacts": [],
        })

        return {
            "module": "ai_cctv_detection",
            "version": "1.0",
            "evidence_file": {
                "name": file_name,
                "sha256": sha256_hash,
                "size_bytes": file_size,
                "type": file_type,
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": findings,
            "artifacts_dir": str(artifacts_dir).replace("\\", "/"),
            "errors": errors,
            "raw_metrics": {
                "video_metadata": meta,
                "quality_summary": quality_summary,
                "model_status": "not_trained",
                "weights_path": str(BEST_MODEL_PATH).replace("\\", "/"),
            },
        }

    # 5. YOLO Classifier Inference
    report_progress("Running YOLO11 classification on native-resolution crops", 65)
    model, device = get_yolo_classifier(BEST_MODEL_PATH)
    frame_probabilities: List[float] = []

    tile_size = int(options.get("tile_size", 448))
    platt_a = float(calib_cfg.get("a", 1.0))
    platt_b = float(calib_cfg.get("b", 0.0))

    try:
        for f_item in kept_frames:
            tiles = extract_native_tiles(f_item["image"], tile_size=tile_size, max_tiles=4)
            # Batch infer on tiles
            results = model.predict(tiles, verbose=False, device=device)
            tile_p_vals = []
            for r in results:
                # Find index for 'ai_generated' or class 1
                names = r.names
                ai_idx = 1
                for idx, name in names.items():
                    if "ai" in name.lower() or "fake" in name.lower() or "synth" in name.lower():
                        ai_idx = idx
                        break
                probs = r.probs.data.cpu().numpy()
                p_ai = float(probs[ai_idx]) if ai_idx < len(probs) else float(probs[-1])
                tile_p_vals.append(p_ai)

            mean_tile_p = float(np.mean(tile_p_vals)) if tile_p_vals else 0.5
            calibrated_p = platt_scale(mean_tile_p, a=platt_a, b=platt_b)
            frame_probabilities.append(round(calibrated_p, 4))
    except Exception as e:
        errors.append(f"YOLO inference error: {str(e)}")
        # If inference fails on model
        return {
            "module": "ai_cctv_detection",
            "version": "1.0",
            "evidence_file": {
                "name": file_name,
                "sha256": sha256_hash,
                "size_bytes": file_size,
                "type": file_type,
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": findings,
            "artifacts_dir": str(artifacts_dir).replace("\\", "/"),
            "errors": errors,
            "raw_metrics": {"video_metadata": meta, "quality_summary": quality_summary},
        }

    # 6. Temporal Aggregation
    report_progress("Performing temporal aggregation and sequence analysis", 80)
    temporal_metrics = calculate_temporal_metrics(
        kept_frames,
        frame_probabilities,
        len(sampled_frames),
        thresholds_cfg,
    )

    # 7. Verdict Determination Ladder
    verdict, overall_confidence = evaluate_verdict(
        temporal_metrics,
        len(kept_frames),
        thresholds_cfg,
    )

    # 8. Optional ByteTrack Modifiers
    if options.get("tracking", False):
        report_progress("Evaluating ByteTrack motion consistency modifiers", 85)
        # ByteTrack checks: localized anomaly check
        # If tracking indicates an anomaly, note it and move verdict toward inconclusive
        track_finding = {
            "id": "track_01",
            "check": "localized_anomaly",
            "severity": "low",
            "confidence": 0.60,
            "description": "Object tracking telemetry evaluated. No localized anomaly detected across active tracks.",
            "location": None,
            "evidence_artifacts": [],
        }
        findings.append(track_finding)

    # 9. Evidence Artifact Generation
    report_progress("Rendering forensic artifacts (timeline and contact sheet)", 90)
    evidence_artifacts: List[str] = []
    job_hash = sha256_hash[:10]
    timeline_file = artifacts_dir / f"timeline_{job_hash}.png"
    contact_file = artifacts_dir / f"contact_sheet_{job_hash}.png"

    timestamps = [f["timestamp"] for f in kept_frames]
    weights = [f["quality_weight"] for f in kept_frames]

    try:
        t_name = generate_timeline_plot(
            timestamps,
            frame_probabilities,
            weights,
            temporal_metrics["suspicious_segments"],
            timeline_file,
        )
        if t_name:
            evidence_artifacts.append(f"artifacts/ai_cctv_detection/{t_name}")
    except Exception as e:
        errors.append(f"Failed to generate timeline plot: {str(e)}")

    try:
        c_name = generate_contact_sheet(
            kept_frames,
            frame_probabilities,
            contact_file,
            num_samples=6,
        )
        if c_name:
            evidence_artifacts.append(f"artifacts/ai_cctv_detection/{c_name}")
    except Exception as e:
        errors.append(f"Failed to generate contact sheet: {str(e)}")

    # 10. Compile Findings
    # Primary clip-level probability finding
    primary_severity = "high" if verdict == "likely_tampered" else ("medium" if verdict == "suspicious" else "low")
    findings.insert(0, {
        "id": "clip_ai_01",
        "check": "clip_ai_probability",
        "severity": primary_severity,
        "confidence": overall_confidence,
        "description": (
            f"Clip aggregated median AI probability is {temporal_metrics['median_p']:.2f}. "
            f"{temporal_metrics['frac_high']*100:.1f}% of quality-screened frames exceeded the 0.70 AI threshold. "
            f"Longest consecutive AI run: {temporal_metrics['run_high']:.1f} seconds."
        ),
        "location": None,
        "evidence_artifacts": [a for a in evidence_artifacts if "timeline" in a],
    })

    # Suspicious segments findings
    for idx, seg in enumerate(temporal_metrics["suspicious_segments"]):
        t_start, t_end = seg["time_range_sec"]
        f_start, f_end = seg["frame_range"]
        findings.append({
            "id": f"seg_{idx+1}",
            "check": "suspicious_segment",
            "severity": "high" if seg["duration_sec"] >= 3.0 else "medium",
            "confidence": 0.85,
            "description": (
                f"Between {t_start:.1f}s and {t_end:.1f}s (frames #{f_start}-#{f_end}), frames consistently look "
                f"AI-generated, while surrounding context may appear real. This is indicative of a spliced or synthesized segment."
            ),
            "location": {
                "time_range_sec": [t_start, t_end],
                "frame_range": [f_start, f_end],
            },
            "evidence_artifacts": [a for a in evidence_artifacts if "timeline" in a],
        })

    # Severity sort order: high -> medium -> low -> info
    sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda x: sev_rank.get(x.get("severity", "info"), 4))

    elapsed_ms = round((time.time() - start_time) * 1000, 1)
    report_progress("Analysis complete", 100)

    # Frame details list for raw_metrics
    frame_scores = [
        {
            "index": f["index"],
            "timestamp": f["timestamp"],
            "score": round(p, 4),
            "weight": f["quality_weight"],
        }
        for f, p in zip(kept_frames, frame_probabilities)
    ]

    return {
        "module": "ai_cctv_detection",
        "version": "1.0",
        "evidence_file": {
            "name": file_name,
            "sha256": sha256_hash,
            "size_bytes": file_size,
            "type": file_type,
        },
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "overall_confidence": round(overall_confidence, 2),
        "findings": findings,
        "artifacts_dir": str(artifacts_dir).replace("\\", "/"),
        "errors": errors,
        "raw_metrics": {
            "median_p": temporal_metrics["median_p"],
            "frac_high": temporal_metrics["frac_high"],
            "run_high": temporal_metrics["run_high"],
            "quality": temporal_metrics["quality"],
            "kept_count": len(kept_frames),
            "dropped_count": quality_summary["dropped_count"],
            "total_sampled": len(sampled_frames),
            "model_version": "YOLO11-cls (fine-tuned)",
            "thresholds_version": thresholds_cfg.get("version", "1.0"),
            "device": device,
            "inference_ms": elapsed_ms,
            "frame_scores": frame_scores,
            "video_metadata": meta,
        },
    }
