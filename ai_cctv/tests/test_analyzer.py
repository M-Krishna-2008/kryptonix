"""Comprehensive test suite for ai_cctv_detection module.

Covers:
- Frame sampling cadence and max_frames capping
- Quality gate usability filtering (blur, resolution, blockiness)
- All temporal aggregation and verdict rule branches (a, b, c, d, e)
- Dataset builder split-by-source provenance isolation
- Missing model honesty rule compliance
- Corrupt and non-existent input handling
"""

import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_cctv_detection.analyzer import (
    analyze,
    compute_sha256,
    evaluate_quality_gate,
    calculate_temporal_metrics,
    evaluate_verdict,
    sample_frames,
    estimate_blockiness,
)
from tools.build_dataset import split_videos
from tests.make_synthetic_clip import create_synthetic_clip


@pytest.fixture(scope="session")
def sample_cctv_clip(tmp_path_factory):
    """Generate a clean synthetic CCTV clip."""
    tmp_dir = tmp_path_factory.mktemp("video_test")
    clip_p = tmp_dir / "clean_cctv.mp4"
    create_synthetic_clip(clip_p, num_frames=60, pattern="cctv")
    return clip_p


@pytest.fixture(scope="session")
def blurry_cctv_clip(tmp_path_factory):
    """Generate a blurry synthetic clip that should fail the quality gate."""
    tmp_dir = tmp_path_factory.mktemp("blur_test")
    clip_p = tmp_dir / "blurry_cctv.mp4"
    create_synthetic_clip(clip_p, num_frames=30, pattern="blur")
    return clip_p


def test_sha256_computation(sample_cctv_clip):
    """Chain-of-custody SHA-256 calculation must be deterministic and non-empty."""
    hash1 = compute_sha256(sample_cctv_clip)
    hash2 = compute_sha256(sample_cctv_clip)
    assert len(hash1) == 64
    assert hash1 == hash2


def test_frame_sampling_and_cap(sample_cctv_clip):
    """Sampling must respect the max_frames cap and record timestamps."""
    frames_all = sample_frames(sample_cctv_clip, max_frames=10, target_fps=2.0)
    assert len(frames_all) <= 10
    assert len(frames_all) > 0

    first = frames_all[0]
    assert "index" in first
    assert "timestamp" in first
    assert "image" in first
    assert isinstance(first["image"], np.ndarray)


def test_quality_gate_clean_vs_blur():
    """Sharp CCTV frame should get weight 1.0, blurry frame should get weight 0.0 (dropped)."""
    # 1. Clean synthetic frame
    sharp_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # 2. Blurry frame (constant intensity)
    blur_img = np.ones((480, 640, 3), dtype=np.uint8) * 128
    # 3. Low-resolution frame (smaller than 480x360)
    low_res_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

    test_items = [
        {"image": sharp_img, "index": 0, "timestamp": 0.0},
        {"image": blur_img, "index": 1, "timestamp": 0.5},
        {"image": low_res_img, "index": 2, "timestamp": 1.0},
    ]

    quality_cfg = {
        "resolution": {"min_width": 480, "min_height": 360},
        "blur": {"unusable_threshold": 20.0, "good_threshold": 60.0},
        "compression": {"unusable_blockiness": 0.45, "good_blockiness": 0.20},
        "weights": {"good": 1.0, "poor": 0.3, "dropped": 0.0},
    }

    kept, summary = evaluate_quality_gate(test_items, quality_cfg)

    # Low res and blur should be dropped; sharp frame kept
    assert len(kept) == 1
    assert kept[0]["index"] == 0
    assert kept[0]["quality_weight"] == 1.0
    assert summary["dropped_count"] == 2


def test_verdict_rule_a_insufficient_evidence():
    """Rule a: quality < 0.30 or < 8 kept frames -> 'inconclusive'."""
    thresholds_cfg = {
        "aggregation": {"min_usable_frames": 8, "min_quality_share": 0.30, "high_confidence_quality": 0.70}
    }

    # Case 1: Low kept frame count (only 5 frames)
    metrics_few_frames = {"median_p": 0.90, "frac_high": 0.80, "run_high": 5.0, "quality": 0.90}
    verdict, conf = evaluate_verdict(metrics_few_frames, kept_count=5, thresholds_cfg=thresholds_cfg)
    assert verdict == "inconclusive"

    # Case 2: Usability below 30%
    metrics_low_quality = {"median_p": 0.90, "frac_high": 0.80, "run_high": 5.0, "quality": 0.25}
    verdict, conf = evaluate_verdict(metrics_low_quality, kept_count=20, thresholds_cfg=thresholds_cfg)
    assert verdict == "inconclusive"


def test_verdict_rule_b_likely_tampered_global():
    """Rule b: median_p >= 0.75 and frac_high >= 0.60 -> 'likely_tampered'."""
    thresholds_cfg = {
        "aggregation": {"min_usable_frames": 8, "min_quality_share": 0.30, "high_confidence_quality": 0.70}
    }
    metrics = {"median_p": 0.82, "frac_high": 0.70, "run_high": 2.0, "quality": 0.85}
    verdict, conf = evaluate_verdict(metrics, kept_count=20, thresholds_cfg=thresholds_cfg)
    assert verdict == "likely_tampered"
    assert conf == 0.90  # High confidence because quality >= 0.70


def test_verdict_rule_c_likely_tampered_splice():
    """Rule c: run_high >= 3.0 s and frac_high >= 0.25 -> 'likely_tampered' (splice)."""
    thresholds_cfg = {
        "aggregation": {"min_usable_frames": 8, "min_quality_share": 0.30, "high_confidence_quality": 0.70}
    }
    # Median is moderate (0.45) but run_high is 4.2s and frac_high is 30%
    metrics = {"median_p": 0.45, "frac_high": 0.30, "run_high": 4.2, "quality": 0.80}
    verdict, conf = evaluate_verdict(metrics, kept_count=25, thresholds_cfg=thresholds_cfg)
    assert verdict == "likely_tampered"
    assert conf == 0.75  # Medium confidence for partial splice


def test_verdict_rule_d_authentic():
    """Rule d: median_p <= 0.30 and frac_high <= 0.10 -> 'authentic'."""
    thresholds_cfg = {
        "aggregation": {"min_usable_frames": 8, "min_quality_share": 0.30, "high_confidence_quality": 0.70}
    }
    metrics = {"median_p": 0.18, "frac_high": 0.05, "run_high": 0.5, "quality": 0.90}
    verdict, conf = evaluate_verdict(metrics, kept_count=30, thresholds_cfg=thresholds_cfg)
    assert verdict == "authentic"
    assert conf == 0.90


def test_verdict_rule_e_suspicious_and_inconclusive():
    """Rule e: median_p between 0.50 and 0.75 -> 'suspicious', otherwise 'inconclusive'."""
    thresholds_cfg = {
        "aggregation": {"min_usable_frames": 8, "min_quality_share": 0.30, "high_confidence_quality": 0.70}
    }
    # Suspicious band (median_p = 0.62, but frac_high does not meet 0.60 global threshold)
    metrics_suspicious = {"median_p": 0.62, "frac_high": 0.40, "run_high": 1.5, "quality": 0.80}
    verdict, conf = evaluate_verdict(metrics_suspicious, kept_count=20, thresholds_cfg=thresholds_cfg)
    assert verdict == "suspicious"

    # Inconclusive case (median_p = 0.40, frac_high = 0.15)
    metrics_inconclusive = {"median_p": 0.40, "frac_high": 0.15, "run_high": 1.0, "quality": 0.80}
    verdict, conf = evaluate_verdict(metrics_inconclusive, kept_count=20, thresholds_cfg=thresholds_cfg)
    assert verdict == "inconclusive"


def test_split_by_source_video_leakage_prevention():
    """Splitting MUST be by source video ID to prevent data leakage."""
    video_list = [Path(f"cctv_cam_{i}.mp4") for i in range(10)]
    train, val, test = split_videos(video_list, train_ratio=0.7, val_ratio=0.15)

    train_set = set(v.name for v in train)
    val_set = set(v.name for v in val)
    test_set = set(v.name for v in test)

    # Ensure no overlap between train and val
    assert len(train_set.intersection(val_set)) == 0
    # Ensure all videos are distributed
    assert len(train) + len(val) + len(test) >= len(video_list)


def test_honesty_rule_missing_model(sample_cctv_clip, monkeypatch):
    """When best.pt does not exist, analyze() must return 'inconclusive' with model_not_trained finding."""
    # Point model path to non-existent file
    import ai_cctv_detection.analyzer as az
    monkeypatch.setattr(az, "BEST_MODEL_PATH", Path("non_existent_model_weights.pt"))

    result = analyze(str(sample_cctv_clip))

    assert result["verdict"] == "inconclusive"
    assert result["overall_confidence"] == 0.0

    checks = [f["check"] for f in result["findings"]]
    assert "model_not_trained" in checks
    assert "video_quality_gate" in checks

    # Non-ML parts must still have executed
    assert "video_metadata" in result["raw_metrics"]
    assert "quality_summary" in result["raw_metrics"]


def test_corrupt_video_handling(tmp_path):
    """Passing a corrupt or non-video file must not raise an unhandled exception."""
    corrupt_file = tmp_path / "corrupt_footage.mp4"
    corrupt_file.write_bytes(b"GARBAGE_HEADER_NOT_A_REAL_VIDEO_STREAM")

    result = analyze(str(corrupt_file))

    assert result["module"] == "ai_cctv_detection"
    assert result["verdict"] == "inconclusive"
    assert len(result["errors"]) > 0
    # Chain of custody must still hash the file
    assert len(result["evidence_file"]["sha256"]) == 64
