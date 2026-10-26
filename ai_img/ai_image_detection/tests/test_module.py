"""
Pytest test suite for ai_image_detection forensic module.
Covers:
  1. Preprocessing output shape (3x224x224) and multi-crop generation.
  2. Determinism of preprocessing and scoring.
  3. Every photo-type rule branch in decide.py.
  4. Graceful error handling for corrupt files, wrong types, and missing weights.
"""

import sys
import tempfile
from pathlib import Path
import pytest
import numpy as np
from PIL import Image
import torch
import torch.nn as nn

MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from analyzer import (
    preprocess_crop_to_tensor,
    generate_crops,
    analyze,
    compute_sha256,
    ingest_image,
    ModelManager
)
from decide import evaluate_decision, load_thresholds


# ---------------------------------------------------------------------------
# 1. Preprocessing & Crop Generation Tests
# ---------------------------------------------------------------------------
def test_preprocess_crop_to_tensor_shape():
    """Verify preprocessing converts a 224x224 PIL image to tensor of exact shape (3, 224, 224)."""
    img = Image.new("RGB", (224, 224), color=(120, 150, 180))
    tensor = preprocess_crop_to_tensor(img)

    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == torch.Size([3, 224, 224])
    assert tensor.dtype == torch.float32


def test_generate_crops_grid_and_padding():
    """Verify 3x3 crop grid generation for large images and padding for small images."""
    # Case A: Large image -> up to 9 crops
    large_img = Image.new("RGB", (800, 600), color=(100, 100, 100))
    crops, boxes, is_padded = generate_crops(large_img)
    assert len(crops) == 9
    assert len(boxes) == 9
    assert is_padded is False
    for c in crops:
        assert c.size == (224, 224)

    # Case B: Small image (< 224px) -> padded to 224x224
    small_img = Image.new("RGB", (150, 180), color=(50, 50, 50))
    crops_s, boxes_s, is_padded_s = generate_crops(small_img)
    assert len(crops_s) == 1
    assert is_padded_s is True
    assert crops_s[0].size == (224, 224)


# ---------------------------------------------------------------------------
# 2. Determinism Tests
# ---------------------------------------------------------------------------
def test_preprocessing_determinism():
    """Verify that preprocessing identical images produces identical tensor values within 1e-4."""
    img = Image.new("RGB", (300, 300), color=(200, 100, 50))
    crops1, _, _ = generate_crops(img)
    crops2, _, _ = generate_crops(img)

    t1 = preprocess_crop_to_tensor(crops1[0]).numpy()
    t2 = preprocess_crop_to_tensor(crops2[0]).numpy()

    np.testing.assert_allclose(t1, t2, atol=1e-5)


def test_decision_determinism():
    """Verify identical inputs to decision logic yield deterministic outputs."""
    res1 = evaluate_decision("camera_photo", 0.85)
    res2 = evaluate_decision("camera_photo", 0.85)
    assert res1 == res2


# ---------------------------------------------------------------------------
# 3. Photo-Type Rule Branching Tests in decide.py
# ---------------------------------------------------------------------------
def test_decide_small_or_blurry():
    """Branch: small_or_blurry must return 'inconclusive' and 'Insufficient quality'."""
    verdict, label, conf, desc, info = evaluate_decision("small_or_blurry", 0.90)
    assert verdict == "inconclusive"
    assert label == "Insufficient quality"
    assert conf == 0.50
    assert "insufficient" in desc.lower()


def test_decide_camera_photo_branches():
    """Branch: camera_photo (fake >= 0.80, real <= 0.20)."""
    # Authentic (<= 0.20)
    v, lbl, conf, _, _ = evaluate_decision("camera_photo", 0.15)
    assert v == "authentic"
    assert lbl == "Real"
    assert conf >= 0.60

    # Likely Fake (>= 0.80)
    v, lbl, conf, _, _ = evaluate_decision("camera_photo", 0.85)
    assert v == "likely_tampered"
    assert lbl == "Likely fake"
    assert conf >= 0.60

    # Uncertain Upper Half (midpoint = 0.50, prob = 0.65) -> suspicious
    v, lbl, _, _, _ = evaluate_decision("camera_photo", 0.65)
    assert v == "suspicious"
    assert lbl == "Uncertain"

    # Uncertain Lower Half (midpoint = 0.50, prob = 0.35) -> inconclusive
    v, lbl, _, _, _ = evaluate_decision("camera_photo", 0.35)
    assert v == "inconclusive"
    assert lbl == "Uncertain"


def test_decide_ai_render_branches():
    """Branch: ai_render (fake >= 0.75, real <= 0.25)."""
    v_fake, _, _, _, _ = evaluate_decision("ai_render", 0.76)
    assert v_fake == "likely_tampered"

    v_real, _, _, _, _ = evaluate_decision("ai_render", 0.24)
    assert v_real == "authentic"

    # Midpoint = 0.50. 0.60 > 0.50 -> suspicious
    v_susp, _, _, _, _ = evaluate_decision("ai_render", 0.60)
    assert v_susp == "suspicious"


def test_decide_social_media_reupload_branches():
    """Branch: social_media_reupload (fake >= 0.90, real <= 0.10)."""
    v_fake, _, _, _, _ = evaluate_decision("social_media_reupload", 0.92)
    assert v_fake == "likely_tampered"

    v_real, _, _, _, _ = evaluate_decision("social_media_reupload", 0.08)
    assert v_real == "authentic"

    # 0.85 is between 0.10 and 0.90, midpoint=0.50 -> suspicious
    v_susp, _, _, _, _ = evaluate_decision("social_media_reupload", 0.85)
    assert v_susp == "suspicious"


def test_decide_screenshot_branches():
    """Branch: screenshot (fake >= 0.95, real <= 0.05)."""
    v_fake, _, _, _, _ = evaluate_decision("screenshot", 0.97)
    assert v_fake == "likely_tampered"

    v_real, _, _, _, _ = evaluate_decision("screenshot", 0.03)
    assert v_real == "authentic"


def test_decide_edited_branches():
    """Branch: edited (fake >= 0.90, real <= 0.10)."""
    v_fake, _, _, _, _ = evaluate_decision("edited", 0.91)
    assert v_fake == "likely_tampered"

    v_real, _, _, _, _ = evaluate_decision("edited", 0.05)
    assert v_real == "authentic"


# ---------------------------------------------------------------------------
# 4. Graceful Error Handling Tests
# ---------------------------------------------------------------------------
def test_corrupt_file_handling():
    """Verify corrupt image file returns standard format with errors, never raises."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xFF\xD8\xFFcorrupted_truncated_jpeg_stream_data_bad_bytes")
        temp_path = f.name

    try:
        res = analyze(temp_path)
        assert isinstance(res, dict)
        assert res["module"] == "ai_image_detection"
        assert res["verdict"] == "inconclusive"
        assert len(res["errors"]) > 0
        assert "ingest" in res["errors"][0].lower() or "failed" in res["errors"][0].lower()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_wrong_type_handling():
    """Verify non-image file returns standard format with error entry."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"This is a text log, not an image file.")
        temp_path = f.name

    try:
        res = analyze(temp_path)
        assert isinstance(res, dict)
        assert res["verdict"] == "inconclusive"
        assert len(res["errors"]) > 0
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_nonexistent_file_handling():
    """Verify non-existent file path returns standard result with error."""
    res = analyze("path/to/nonexistent/evidence_file_12345.png")
    assert isinstance(res, dict)
    assert res["verdict"] == "inconclusive"
    assert any("not found" in err.lower() for err in res["errors"])


def test_missing_weights_graceful_error(monkeypatch):
    """Verify missing weights return instructions in 'errors' field and do not crash."""
    # Point weights to non-existent files
    fake_clip = MODULE_DIR / "models" / "clip" / "nonexistent_vit.pt"
    fake_probe = MODULE_DIR / "models" / "nonexistent_probe.pth"

    import analyzer
    monkeypatch.setattr(analyzer, "CLIP_WEIGHTS_PATH", fake_clip)
    monkeypatch.setattr(analyzer, "PROBE_WEIGHTS_PATH", fake_probe)

    # Reset ModelManager instance
    analyzer.ModelManager._instance = None

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (300, 300), color=(128, 128, 128))
        img.save(f, format="PNG")
        temp_path = f.name

    try:
        res = analyze(temp_path)
        assert isinstance(res, dict)
        assert len(res["errors"]) > 0
        # Check error contains instructions
        err_msg = " ".join(res["errors"])
        assert "setup_model.md" in err_msg or "weights" in err_msg.lower()
    finally:
        Path(temp_path).unlink(missing_ok=True)
        analyzer.ModelManager._instance = None


# ---------------------------------------------------------------------------
# 5. FastAPI Router & Schema Validation Tests
# ---------------------------------------------------------------------------
def test_pydantic_schema_compliance():
    """Verify analyzer output conforms strictly to Pydantic ModuleResult schema."""
    from schemas import ModuleResult

    # Run on synthetic authentic sample
    sample_path = MODULE_DIR / "tests" / "samples" / "sample_camera_authentic.jpg"
    res = analyze(str(sample_path))

    # Validate with Pydantic
    validated = ModuleResult.model_validate(res)
    assert validated.module == "ai_image_detection"
    assert validated.version == "1.0"
    assert validated.evidence_file.sha256 != ""
    assert validated.verdict in ["authentic", "suspicious", "likely_tampered", "inconclusive"]


def test_api_router_endpoints():
    """Verify FastAPI router health and analyze endpoints."""
    from fastapi.testclient import TestClient
    from main_standalone import app

    client = TestClient(app)

    # 1. Health Endpoint
    resp_health = client.get("/api/ai_image_detection/health")
    assert resp_health.status_code == 200
    assert resp_health.json() == {"status": "ok", "module": "ai_image_detection"}

    # 2. Analyze Endpoint (Multipart Upload)
    sample_path = MODULE_DIR / "tests" / "samples" / "sample_camera_authentic.jpg"
    with open(sample_path, "rb") as f:
        resp_upload = client.post(
            "/api/ai_image_detection/analyze",
            files={"file": ("sample_camera_authentic.jpg", f, "image/jpeg")}
        )

    assert resp_upload.status_code == 200
    result = resp_upload.json()
    assert result["module"] == "ai_image_detection"
    assert "verdict" in result
    assert "findings" in result
    assert "raw_metrics" in result

    # 3. Artifact Endpoint (Serve heatmap)
    findings = result.get("findings", [])
    artifact_found = False
    for f in findings:
        if f.get("evidence_artifacts"):
            art_name = Path(f["evidence_artifacts"][0]).name
            resp_art = client.get(f"/api/ai_image_detection/artifacts/{art_name}")
            assert resp_art.status_code == 200
            assert resp_art.headers["content-type"].startswith("image/")
            artifact_found = True
            break
    assert artifact_found is True

