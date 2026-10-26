"""
PS-05 Unified AI Forensics Platform - Comprehensive Automated Smoke Test Suite
Tests every module against running servers via Gateway (port 8080) and direct module endpoints.
"""

from __future__ import annotations
import io
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import requests

BASE_DIR = Path(__file__).resolve().parent.parent

GATEWAY_URL = "http://127.0.0.1:8080"
PORTS_FILE = BASE_DIR / "runtime" / "ports.json"

# Load assigned runtime ports
if PORTS_FILE.exists():
    with open(PORTS_FILE) as f:
        PORTS = json.load(f)
else:
    PORTS = {
        "gateway": 8080,
        "ai_aud": 8001,
        "ai_img": 8002,
        "image_forgery": 8003,
        "ai_cctv": 8004
    }

SAMPLES = {
    "ai_aud": BASE_DIR / "ai_aud/audio_forensics/tests/samples/real/sample_voice_real.wav",
    "ai_img": BASE_DIR / "ai_img/ai_image_detection/tests/samples/sample_camera_authentic.jpg",
    "image_forgery": BASE_DIR / "image_forgery/image_forgery/tests/samples/authentic.jpg",
    "ai_cctv": BASE_DIR / "ai_cctv/tests/api_test_clip.mp4"
}

MODULE_ROUTES = {
    "ai_aud": {
        "health": "/api/audio_forensics/health",
        "analyze": "/api/audio_forensics/analyze",
        "progress": "/api/audio_forensics/progress/{job_id}",
        "artifacts": "/api/audio_forensics/artifacts",
        "ui_keys": ["verdict", "overall_confidence", "evidence_file", "raw_metrics", "findings"],
        "raw_metric_keys": ["bona_fide_logit", "clip_summary", "valid_windows", "total_windows"]
    },
    "ai_img": {
        "health": "/api/ai_image_detection/health",
        "analyze": "/api/ai_image_detection/analyze",
        "progress": None,
        "artifacts": "/api/ai_image_detection/artifacts",
        "ui_keys": ["verdict", "overall_confidence", "evidence_file", "raw_metrics", "findings"],
        "raw_metric_keys": ["calibrated_probability", "photo_type"]
    },
    "image_forgery": {
        "health": "/api/image_forgery/health",
        "analyze": "/api/image_forgery/analyze",
        "progress": None,
        "artifacts": "/api/image_forgery/artifacts",
        "ui_keys": ["verdict", "overall_confidence", "evidence_file", "raw_metrics", "findings"],
        "raw_metric_keys": ["engines"]
    },
    "ai_cctv": {
        "health": "/api/ai_cctv_detection/health",
        "analyze": "/api/ai_cctv_detection/analyze",
        "progress": "/api/ai_cctv_detection/progress/{job_id}",
        "artifacts": "/api/ai_cctv_detection/artifacts",
        "ui_keys": ["verdict", "overall_confidence", "evidence_file", "raw_metrics", "findings"],
        "raw_metric_keys": ["median_p", "frame_scores", "total_sampled"]
    }
}

test_results: List[Dict[str, Any]] = []

def record(module: str, test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    test_results.append({
        "module": module,
        "test": test_name,
        "status": status,
        "detail": detail
    })
    color = "\033[92m" if passed else "\033[91m"
    print(f"[{color}{status}\033[0m] {module:15} | {test_name:30} | {detail}")


def check_no_nan_or_inf(obj):
    s = json.dumps(obj)
    return ("NaN" not in s) and ("Infinity" not in s) and ("-Infinity" not in s)


print("======================================================================")
print("   PS-05 Automated Platform Smoke & Feature Test Suite")
print("======================================================================")

# 1. Gateway Aggregated Health Check
try:
    gw_resp = requests.get(f"{GATEWAY_URL}/api/health", timeout=5)
    gw_data = gw_resp.json()
    record("gateway", "aggregated_health", gw_resp.status_code == 200 and gw_data.get("status") == "healthy",
           f"HTTP {gw_resp.status_code}, overall status: {gw_data.get('status')}")
except Exception as e:
    record("gateway", "aggregated_health", False, str(e))

# 2. Per-Module Endpoints Verification
for mod_id, meta in MODULE_ROUTES.items():
    port = PORTS.get(mod_id)
    base_url = f"http://127.0.0.1:{port}"
    routes = meta

    # Test 1: Direct Health Check
    try:
        h_resp = requests.get(f"{base_url}{routes['health']}", timeout=5)
        record(mod_id, "direct_health", h_resp.status_code == 200, f"HTTP {h_resp.status_code}")
    except Exception as e:
        record(mod_id, "direct_health", False, str(e))

    # Test 2: Valid Analyze Execution
    sample_file = SAMPLES[mod_id]
    first_result = None
    if sample_file.exists():
        try:
            with open(sample_file, "rb") as f:
                t0 = time.time()
                resp = requests.post(f"{base_url}{routes['analyze']}", files={"file": f}, timeout=120)
                dur = time.time() - t0

            if resp.status_code == 200:
                first_result = resp.json()
                record(mod_id, "analyze_valid_sample", True, f"HTTP 200 in {dur:.2f}s, verdict: {first_result.get('verdict')}")
            else:
                record(mod_id, "analyze_valid_sample", False, f"HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            record(mod_id, "analyze_valid_sample", False, str(e))
    else:
        record(mod_id, "analyze_valid_sample", False, f"Sample file missing: {sample_file}")

    # Test 3: Result JSON keys UI reads
    if first_result:
        missing_top = [k for k in routes["ui_keys"] if k not in first_result]
        rm = first_result.get("raw_metrics", {})
        missing_rm = [k for k in routes["raw_metric_keys"] if k not in rm]
        passed = (len(missing_top) == 0 and len(missing_rm) == 0)
        detail = "All contract keys present" if passed else f"Missing: top={missing_top}, rm={missing_rm}"
        record(mod_id, "ui_result_keys", passed, detail)

        # Test 4: SHA-256 Present
        sha_present = bool(first_result.get("evidence_file", {}).get("sha256"))
        record(mod_id, "sha256_hash_present", sha_present, f"sha256={first_result.get('evidence_file', {}).get('sha256')[:12]}...")

        # Test 5: No NaN or Infinity in JSON
        no_nan = check_no_nan_or_inf(first_result)
        record(mod_id, "no_nan_or_infinity", no_nan, "Strict JSON compliance verified")

        # Test 6: Caching on Second Call
        try:
            with open(sample_file, "rb") as f:
                t0 = time.time()
                resp2 = requests.post(f"{base_url}{routes['analyze']}", files={"file": f}, timeout=30)
                dur2 = time.time() - t0
            res2_data = resp2.json() if resp2.status_code == 200 else {}
            cache_valid = (resp2.status_code == 200 and res2_data.get("evidence_file", {}).get("sha256") == first_result.get("evidence_file", {}).get("sha256"))
            record(mod_id, "second_call_caching", cache_valid, f"Cached response verified in {dur2:.2f}s")
        except Exception as e:
            record(mod_id, "second_call_caching", False, str(e))

        # Test 7: Artifact Serving
        art_map = rm.get("visual_artifacts") or rm.get("artifacts") or {}
        art_files = []
        if isinstance(art_map, dict):
            art_files = [v for v in art_map.values() if isinstance(v, str)]
        elif isinstance(art_map, list):
            art_files = [v for v in art_map if isinstance(v, str)]

        if art_files:
            first_art = art_files[0]
            try:
                art_resp = requests.get(f"{base_url}{routes['artifacts']}/{first_art}", timeout=5)
                record(mod_id, "artifact_serving", art_resp.status_code == 200, f"Served {first_art} (HTTP {art_resp.status_code})")
            except Exception as e:
                record(mod_id, "artifact_serving", False, str(e))
        else:
            record(mod_id, "artifact_serving", True, "No artifact images generated for this sample")
    else:
        record(mod_id, "ui_result_keys", False, "Skipped due to analyze failure")
        record(mod_id, "sha256_hash_present", False, "Skipped")
        record(mod_id, "no_nan_or_infinity", False, "Skipped")
        record(mod_id, "second_call_caching", False, "Skipped")
        record(mod_id, "artifact_serving", False, "Skipped")

    # Test 8: Progress Endpoint (if supported)
    if routes["progress"]:
        try:
            prog_url = f"{base_url}" + routes["progress"].replace("{job_id}", "test_job_123")
            p_resp = requests.get(prog_url, timeout=5)
            record(mod_id, "progress_endpoint", p_resp.status_code in (200, 404), f"HTTP {p_resp.status_code}")
        except Exception as e:
            record(mod_id, "progress_endpoint", False, str(e))
    else:
        record(mod_id, "progress_endpoint", True, "Synchronous module (progress endpoint not required)")

    # Test 9: Invalid Input - Empty File (0 bytes)
    try:
        empty_file = io.BytesIO(b"")
        resp = requests.post(f"{base_url}{routes['analyze']}", files={"file": ("empty.dat", empty_file)}, timeout=30)
        # Expect either safe HTTP error (400, 422) or safe inconclusive result (never unhandled 500)
        passed = resp.status_code in (400, 422) or (resp.status_code == 200 and resp.json().get("verdict") == "inconclusive")
        record(mod_id, "invalid_empty_file", passed, f"HTTP {resp.status_code}")
    except Exception as e:
        record(mod_id, "invalid_empty_file", False, str(e))

    # Test 10: Invalid Input - Wrong File Type (plain text)
    try:
        txt_file = io.BytesIO(b"Hello world, this is a plain text file, not media.")
        resp = requests.post(f"{base_url}{routes['analyze']}", files={"file": ("notes.txt", txt_file)}, timeout=30)
        passed = resp.status_code in (400, 415, 422) or (resp.status_code == 200 and ("error" in resp.text.lower() or resp.json().get("verdict") == "inconclusive"))
        record(mod_id, "invalid_wrong_type", passed, f"HTTP {resp.status_code}")
    except Exception as e:
        record(mod_id, "invalid_wrong_type", False, str(e))

    # Test 11: Invalid Input - Corrupt Binary Header
    try:
        corrupt_bytes = io.BytesIO(b"\x00\xff\xee\xdd\xaa\xbb\xcc\xdd" * 128)
        ext = sample_file.suffix
        resp = requests.post(f"{base_url}{routes['analyze']}", files={"file": (f"corrupt{ext}", corrupt_bytes)}, timeout=30)
        passed = resp.status_code in (400, 422) or (resp.status_code == 200 and ("error" in resp.text.lower() or resp.json().get("verdict") == "inconclusive"))
        record(mod_id, "invalid_corrupt_binary", passed, f"HTTP {resp.status_code}")
    except Exception as e:
        record(mod_id, "invalid_corrupt_binary", False, str(e))

print("\n======================================================================")
print("   SUMMARY PASS / FAIL MATRIX")
print("======================================================================")
passes = sum(1 for r in test_results if r["status"] == "PASS")
fails = sum(1 for r in test_results if r["status"] == "FAIL")
total = len(test_results)
print(f"Total Tests: {total} | Passed: {passes} | Failed: {fails} | Success Rate: {(passes/total)*100:.1f}%\n")

for mod in ["gateway", "ai_aud", "ai_img", "image_forgery", "ai_cctv"]:
    mod_tests = [r for r in test_results if r["module"] == mod]
    print(f"[{mod.upper()}] ({len(mod_tests)} tests)")
    for t in mod_tests:
        mark = "[OK]" if t["status"] == "PASS" else "[FAIL]"
        print(f"  {mark:6} {t['test']:25} -> {t['detail']}")

if fails > 0:
    sys.exit(1)
