import math
import json
import numpy as np
import pytest
import soundfile as sf
import tempfile
from pathlib import Path

from audio_forensics.analyzer import calculate_verdict_and_confidence, analyze
from audio_forensics.config import DEFAULT_THRESHOLDS
from audio_forensics.audio_preprocess import preprocess_and_window, resample_to_16k, decode_audio


def make_dummy_window_meta(n_windows: int, hop_sec: float = 2.0, win_dur: float = 4.04, speech_ratio: float = 0.85):
    meta = []
    for i in range(n_windows):
        s = i * hop_sec
        e = s + win_dur
        meta.append({
            "index": i,
            "start_sec": s,
            "end_sec": e,
            "is_padded": False,
            "speech_ratio": speech_ratio,
            "has_speech": speech_ratio >= 0.50,
        })
    return meta


def test_all_windows_non_speech_returns_numeric_score_and_low_speech_finding():
    """(a) all windows classified as non-speech still returns a numeric score plus the low_speech_content finding."""
    # 5 windows, all with speech_ratio = 0.10 (< 0.50) -> speech_windows = 0
    logits = np.array([2.1, 2.3, 1.9, 2.0, 2.2], dtype=np.float32)
    meta = make_dummy_window_meta(5, speech_ratio=0.10)

    verdict, confidence, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )

    # Must return a valid numeric score (fallback over all valid windows)
    assert metrics is not None, "Summary metrics must not be None"
    assert isinstance(metrics["median_logit"], float)
    assert not math.isnan(metrics["median_logit"])
    assert metrics["median_logit"] == pytest.approx(2.1, rel=1e-2)

    # Must include the low_speech_content finding
    finding_checks = [f.check if hasattr(f, "check") else f.get("check") for f in findings]
    assert "low_speech_content" in finding_checks, "Must add 'low_speech_content' finding"

    # Window metrics must reflect 0 speech windows and 5 valid windows
    assert metrics["speech_windows_count"] == 0
    assert metrics["valid_windows_count"] == 5
    assert metrics["total_windows_count"] == 5

    # Score unavailable reason should be None because score was successfully computed via fallback
    assert metrics["score_unavailable_reason"] is None


def test_silent_file_returns_null_with_clear_reason_and_no_crash():
    """(b) a silent file returns null with a clear reason and no crash."""
    logits = np.array([0.0, 0.0], dtype=np.float32)
    meta = make_dummy_window_meta(2, speech_ratio=0.0)

    verdict, confidence, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=5.0,
        is_silent=True,
        model_installed=True,
    )

    assert verdict == "inconclusive"
    assert confidence is None, "Confidence must be null/None when score cannot be computed"
    assert metrics is not None, "Summary metrics should contain reason"
    assert metrics["median_logit"] is None, "Median logit must be None for silent file"
    reason = metrics.get("score_unavailable_reason")
    assert reason is not None and len(reason) > 0, "Must provide a clear human-readable reason"
    assert "silent" in reason.lower()

    finding_checks = [f.check if hasattr(f, "check") else f.get("check") for f in findings]
    assert "silent_audio" in finding_checks


def test_window_with_nan_logit_is_excluded_and_counted():
    """(c) a window with NaN/inf logit is excluded and counted in invalid_windows."""
    logits = np.array([2.5, np.nan, 2.3, np.inf, 2.1], dtype=np.float32)
    meta = make_dummy_window_meta(5, speech_ratio=0.9)

    verdict, confidence, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )

    assert metrics is not None
    assert metrics["invalid_windows_count"] == 2
    assert metrics["valid_windows_count"] == 3
    assert metrics["total_windows_count"] == 5
    assert isinstance(metrics["median_logit"], float)
    assert not math.isnan(metrics["median_logit"])
    # Median of [2.5, 2.3, 2.1] is 2.3
    assert metrics["median_logit"] == pytest.approx(2.3, rel=1e-2)


def test_json_contains_no_nan_or_infinity():
    """(d) JSON contains no NaN or Infinity."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    try:
        # Create 5s 16kHz audio with sine wave
        t = np.linspace(0, 5, 5 * 16000, endpoint=False, dtype=np.float32)
        sine = 0.5 * np.sin(2 * np.pi * 440 * t)
        sf.write(tmp_path, sine, 16000)

        result = analyze(tmp_path)
        json_str = json.dumps(result, allow_nan=False)
        assert "NaN" not in json_str
        assert "Infinity" not in json_str
        assert "-Infinity" not in json_str

        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_resampling_48k_and_44k():
    """(e) a 48 kHz and a 44.1 kHz file both resample correctly (sample count check within 1 sample)."""
    duration_sec = 3.5

    # 48 kHz test
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f48:
        p48 = f48.name
    # 44.1 kHz test
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f44:
        p44 = f44.name

    try:
        t48 = np.linspace(0, duration_sec, int(duration_sec * 48000), endpoint=False, dtype=np.float32)
        w48 = 0.3 * np.sin(2 * np.pi * 300 * t48)
        sf.write(p48, w48, 48000)

        t44 = np.linspace(0, duration_sec, int(duration_sec * 44100), endpoint=False, dtype=np.float32)
        w44 = 0.3 * np.sin(2 * np.pi * 300 * t44)
        sf.write(p44, w44, 44100)

        prep_48 = preprocess_and_window(p48)
        expected_samples = int(duration_sec * 16000)
        assert prep_48["sample_rate"] == 16000
        assert prep_48["orig_sr"] == 48000
        assert abs(len(prep_48["waveform"]) - expected_samples) <= 1

        prep_44 = preprocess_and_window(p44)
        assert prep_44["sample_rate"] == 16000
        assert prep_44["orig_sr"] == 44100
        assert abs(len(prep_44["waveform"]) - expected_samples) <= 1
    finally:
        Path(p48).unlink(missing_ok=True)
        Path(p44).unlink(missing_ok=True)


def test_ui_facing_json_keys():
    """(f) the UI-facing JSON always includes the keys the frontend reads."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    try:
        t = np.linspace(0, 4.5, int(4.5 * 16000), endpoint=False, dtype=np.float32)
        audio = 0.4 * np.sin(2 * np.pi * 400 * t)
        sf.write(tmp_path, audio, 16000)

        result = analyze(tmp_path)

        # Top-level keys
        assert "verdict" in result
        assert "overall_confidence" in result
        assert "score_unavailable_reason" in result
        assert "evidence_file" in result
        assert "raw_metrics" in result
        assert "findings" in result

        rm = result["raw_metrics"]
        # Required raw_metrics keys read by ui.js and module.js
        assert "bona_fide_logit" in rm
        assert "windows_analyzed" in rm
        assert "valid_windows" in rm
        assert "invalid_windows" in rm
        assert "speech_windows" in rm
        assert "total_windows" in rm
        assert "clip_summary" in rm
        assert "median_logit" in rm["clip_summary"]
        assert "audio_info" in rm
        assert "orig_sr" in rm["audio_info"]
    finally:
        Path(tmp_path).unlink(missing_ok=True)
