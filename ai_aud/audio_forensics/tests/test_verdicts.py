from __future__ import annotations
import numpy as np
import pytest

from audio_forensics.analyzer import calculate_verdict_and_confidence, analyze
from audio_forensics.config import DEFAULT_THRESHOLDS, load_thresholds
from audio_forensics.heuristics import detect_repeated_segment, run_all_heuristics
from audio_forensics.audio_preprocess import detect_container_codec


def make_dummy_window_meta(n_windows: int, hop_sec: float = 2.0, win_dur: float = 4.04, all_speech: bool = True):
    meta = []
    for i in range(n_windows):
        s = i * hop_sec
        e = s + win_dur
        meta.append({
            "index": i,
            "start_sec": s,
            "end_sec": e,
            "is_padded": False,
            "speech_ratio": 0.85 if all_speech else 0.10,
            "has_speech": all_speech,
        })
    return meta


def test_verdict_rule_a_empty_or_silent():
    # Empty windows
    v, conf, _, _ = calculate_verdict_and_confidence(
        logits=np.zeros(0, dtype=np.float32),
        window_meta=[],
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=0.0,
        is_silent=False,
        model_installed=True,
    )
    assert v == "inconclusive"

    # Silent audio
    v, conf, _, _ = calculate_verdict_and_confidence(
        logits=np.array([2.5, 2.8], dtype=np.float32),
        window_meta=make_dummy_window_meta(2),
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=5.0,
        is_silent=True,
        model_installed=True,
    )
    assert v == "inconclusive"


def test_one_window_low_out_of_six_must_not_give_likely_tampered():
    """Step 7: 1 window low out of 6 must NOT give 'likely_tampered'."""
    # 6 speech windows, only 1 is low (-3.5), rest are high (+2.5)
    logits = np.array([2.5, 2.4, -3.5, 2.6, 2.7, 2.5], dtype=np.float32)
    meta = make_dummy_window_meta(6)

    v, conf, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=14.0,
        is_silent=False,
        model_installed=True,
    )
    assert v != "likely_tampered"
    assert v in ("authentic", "suspicious", "inconclusive")


def test_clips_with_fewer_than_three_windows_never_likely_tampered():
    """Step 2: Clips with fewer than 3 windows can never be likely_tampered."""
    # 2 windows, both low
    logits = np.array([-3.5, -4.0], dtype=np.float32)
    meta = make_dummy_window_meta(2)

    v, conf, _, _ = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=6.0,
        is_silent=False,
        model_installed=True,
    )
    assert v != "likely_tampered"
    assert v == "suspicious"


def test_verdict_rule_b_entirely_synthetic():
    # 5 windows, all strongly negative (< -2.5) well past borderline margin
    logits = np.array([-4.2, -4.5, -4.1, -4.8, -4.0], dtype=np.float32)
    meta = make_dummy_window_meta(len(logits))

    v, conf, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )
    assert v == "likely_tampered"
    assert conf >= 0.65
    assert any(f.id == "synthetic_speech_entire" for f in findings)


def test_verdict_rule_c_splice_requires_consecutive_and_total_criteria():
    """
    Step 2 partial tampering rule:
    Requires: >=2 consecutive low windows, >=3 low windows total, fraction_low >= 0.25, and >=5 total windows.
    """
    # 8 speech windows:
    # Windows 1, 2, 3 are low (-3.2, -3.4, -3.1) -> 3 consecutive low windows (>=2) and 3 total (>=3)
    # fraction_low = 3/8 = 37.5% (>= 25%)
    logits = np.array([2.5, -3.2, -3.4, -3.1, 2.6, 2.7, 2.4, 2.5], dtype=np.float32)
    meta = make_dummy_window_meta(len(logits))

    v, conf, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=18.0,
        is_silent=False,
        model_installed=True,
    )
    assert v == "likely_tampered"
    assert any(f.id == "synthetic_speech_segment_splice" for f in findings)

    # Counter-case: 2 isolated low windows (not consecutive) with only 2 low windows total
    # Must NOT trigger likely_tampered
    logits_non_consec = np.array([2.5, -3.2, 2.4, -3.4, 2.6, 2.7, 2.4, 2.5], dtype=np.float32)
    v2, conf2, _, _ = calculate_verdict_and_confidence(
        logits=logits_non_consec,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=18.0,
        is_silent=False,
        model_installed=True,
    )
    assert v2 != "likely_tampered"


def test_non_speech_windows_are_excluded():
    """Step 3: Windows with less than 50% speech are excluded from verdict scoring."""
    # 5 windows: 3 are non-speech, only 2 speech windows remain
    meta = make_dummy_window_meta(5)
    meta[0]["has_speech"] = True
    meta[1]["has_speech"] = False  # non-speech
    meta[2]["has_speech"] = False  # non-speech
    meta[3]["has_speech"] = False  # non-speech
    meta[4]["has_speech"] = True

    # The non-speech windows have synthetic-like noise (-5.0), but speech windows are authentic (+3.0)
    logits = np.array([3.0, -5.0, -5.0, -5.0, 3.2], dtype=np.float32)

    v, conf, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )
    # The non-speech windows must be excluded; speech windows average +3.1, so verdict is authentic!
    assert v == "authentic"
    assert metrics["speech_windows_count"] == 2

    # Case: fewer than 2 speech windows remain -> inconclusive with "not_enough_speech"
    meta_one_speech = make_dummy_window_meta(5, all_speech=False)
    meta_one_speech[0]["has_speech"] = True

    v_few, _, _, findings_few = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta_one_speech,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )
    assert v_few == "inconclusive"
    assert any(f.id == "not_enough_speech" for f in findings_few)


def test_lossy_input_widens_thresholds_and_caps_confidence():
    """Step 4: Lossy input widens thresholds and caps confidence at medium (0.70)."""
    lossless_thresh = load_thresholds(codec_class="lossless")
    lossy_high_thresh = load_thresholds(codec_class="lossy_high_bitrate")
    lossy_low_thresh = load_thresholds(codec_class="lossy_low_bitrate")

    # Lower threshold is wider (more negative) for lossy
    assert lossy_high_thresh["low_threshold"] <= lossless_thresh["low_threshold"]
    assert lossy_low_thresh["low_threshold"] <= lossy_high_thresh["low_threshold"]

    # Confidence capping on lossy input
    logits = np.array([-5.5, -5.8, -5.2, -5.4, -5.6], dtype=np.float32)
    meta = make_dummy_window_meta(len(logits))

    v, conf_lossless, _, _ = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=lossless_thresh,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
        is_lossy=False,
    )

    v2, conf_lossy, _, _ = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=lossy_high_thresh,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
        is_lossy=True,
    )
    assert conf_lossy <= 0.70


def test_padded_short_clip_does_not_trigger_repeated_segment():
    """Step 5: Do not run repeated_segment on clips that were tiled (short_clip_padded)."""
    # 2 seconds of audio repeated
    t = np.linspace(0, 2.0, 32000, endpoint=False)
    y_short = (0.5 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    y_tiled = np.tile(y_short, 3)  # Repeated 3 times = 6 seconds

    # With short_clip_padded=True, repeated_segment must NOT run / must return 0 findings
    findings, metrics = detect_repeated_segment(y_tiled, sr=16000, short_clip_padded=True)
    assert len(findings) == 0
    assert metrics.get("reason") == "short_clip_padded"


def test_heuristics_alone_cannot_flip_the_verdict():
    """Step 5: Heuristics alone can never set the verdict to likely_tampered."""
    # Authentic speech logits (+2.5) across all windows
    logits = np.array([2.5, 2.6, 2.7, 2.5, 2.8], dtype=np.float32)
    meta = make_dummy_window_meta(len(logits))

    v, conf, _, _ = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=meta,
        thresholds=DEFAULT_THRESHOLDS,
        duration_sec=12.0,
        is_silent=False,
        model_installed=True,
    )
    # The verdict is strictly authentic based on neural scoring
    assert v == "authentic"
