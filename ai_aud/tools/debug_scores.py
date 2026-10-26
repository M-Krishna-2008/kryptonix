#!/usr/bin/env python3
"""
Diagnostic tool for inspecting W2V2-AASIST raw scores and verdict logic.
Usage:
    python tools/debug_scores.py <audio_file>
"""

import sys
import os
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audio_forensics.audio_preprocess import preprocess_and_window
from audio_forensics.model_aasist import score_windows, check_models_available
from audio_forensics.config import load_thresholds
from audio_forensics.analyzer import calculate_verdict_and_confidence


def debug_file(file_path: str | Path, thresholds: dict | None = None) -> dict:
    path = Path(file_path)
    if not path.is_file():
        print(f"[ERROR] File not found: {file_path}")
        return {"error": "File not found"}

    prep_res = preprocess_and_window(path)
    flags = prep_res.get("flags", {})
    y = prep_res.get("waveform", np.zeros(0, dtype=np.float32))
    windows = prep_res.get("windows", [])
    window_meta = prep_res.get("window_meta", [])
    duration_sec = prep_res.get("duration_sec", 0.0)
    codec_info = prep_res.get("codec_info", {})
    codec_class = codec_info.get("codec_class", "lossless")
    is_lossy = codec_info.get("is_lossy", False)

    if thresholds is None:
        thresholds = load_thresholds(codec_class=codec_class)

    low_thresh = float(thresholds["low_threshold"])
    high_thresh = float(thresholds["high_threshold"])

    print("=" * 70)
    print(f"FILE: {path.name}")
    print(f"Path: {path}")
    print(f"Duration: {duration_sec:.2f} s | Windows: {len(windows)}")
    print(f"Codec info: {codec_info.get('codec')} ({codec_class}, bitrate: {codec_info.get('bitrate_kbps')} kbps, lossy: {is_lossy})")
    print(f"Thresholds applied: low={low_thresh}, high={high_thresh}, suspicious_margin={thresholds.get('suspicious_margin')}")
    print(f"Flags: short_clip_padded={flags.get('short_clip_padded')}, silent={flags.get('is_silent')}, speech_windows={flags.get('speech_windows_count')}/{len(windows)}")
    print("-" * 70)

    is_avail, missing = check_models_available()
    if not is_avail:
        print(f"[ERROR] Model weights not installed: {missing}")
        return {"error": "Model weights missing"}

    if len(windows) == 0 or flags.get("is_silent"):
        rule_fired = "Rule (a): fewer than 1 usable window or silence"
        verdict = "inconclusive"
        print(f"Verdict: {verdict}")
        print(f"Rule fired: {rule_fired}")
        return {
            "file": path.name,
            "duration": duration_sec,
            "windows": 0,
            "median": None,
            "min": None,
            "fraction_low": 0.0,
            "longest_low_run": 0.0,
            "rule_fired": rule_fired,
            "verdict": verdict,
        }

    logits, err = score_windows(windows)
    if err or len(logits) == 0:
        print(f"[ERROR] Inference failed: {err}")
        return {"error": str(err)}

    print(f"{'Window':<7} {'Time Range (s)':<17} {'Speech?':<9} {'Bona-fide Logit':<18} {'Status'}")
    print("-" * 70)

    for idx, (logit, wmeta) in enumerate(zip(logits, window_meta)):
        has_sp = wmeta.get("has_speech", True)
        sp_ratio = wmeta.get("speech_ratio", 1.0)
        sp_str = f"YES ({sp_ratio:.0%})" if has_sp else f"NO ({sp_ratio:.0%})"
        if not has_sp:
            status = "EXCLUDED (no speech)"
        elif logit <= low_thresh:
            status = "LOW (spoof-like)"
        elif logit >= high_thresh:
            status = "HIGH (authentic-like)"
        else:
            status = "UNCERTAIN"
        time_str = f"{wmeta['start_sec']:.2f}s - {wmeta['end_sec']:.2f}s"
        print(f"{idx+1:<7} {time_str:<17} {sp_str:<9} {logit:<18.4f} {status}")

    # Run verdict engine
    verdict, confidence, metrics, findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=window_meta,
        thresholds=thresholds,
        duration_sec=duration_sec,
        is_silent=flags.get("is_silent", False),
        model_installed=True,
        is_lossy=is_lossy,
    )

    median_logit = metrics.get("median_logit") if metrics else None
    min_logit = metrics.get("min_logit") if metrics else None
    fraction_low = metrics.get("fraction_low", 0.0) if metrics else 0.0
    longest_low_run = metrics.get("longest_low_run_s", 0.0) if metrics else 0.0
    run_range = metrics.get("longest_low_run_range") if metrics else None

    # Identify rule fired for display
    rule_fired = "None"
    if verdict == "likely_tampered":
        if any(f.id == "synthetic_speech_entire" for f in findings):
            rule_fired = f"Rule (b): whole recording median logit ({median_logit:.2f}) <= low_thresh ({low_thresh:.2f}) and fraction_low ({fraction_low:.0%}) >= 60%"
        elif any(f.id == "synthetic_speech_segment_splice" for f in findings):
            rule_fired = f"Rule (c): partial splice (run={longest_low_run:.1f}s, low={fraction_low:.0%}, total_windows>={thresholds.get('partial_min_total_windows')})"
    elif verdict == "authentic":
        rule_fired = f"Rule (d): median logit ({median_logit:.2f}) >= high_thresh ({high_thresh:.2f}) and fraction_low ({fraction_low:.0%}) <= 5%"
    elif verdict == "suspicious":
        rule_fired = f"Rule (e): suspicious margin or borderline score (median logit = {median_logit})"
    else:
        if any(f.id == "not_enough_speech" for f in findings):
            rule_fired = "Step 3 VAD: fewer than 2 speech windows ('not enough speech')"
        else:
            rule_fired = "Rule (e): inconclusive (uncertain band or conflicting signals)"

    print("-" * 70)
    print(f"Median logit (speech):       {f'{median_logit:.4f}' if median_logit is not None else 'N/A'}")
    print(f"Min logit (speech):          {f'{min_logit:.4f}' if min_logit is not None else 'N/A'}")
    print(f"Fraction below low_thresh:   {fraction_low:.2%} (threshold: {low_thresh})")
    print(f"Longest low run:             {longest_low_run:.2f} s (range: {run_range})")
    print(f"Verdict:                     {verdict} (confidence: {confidence:.0%})")
    print(f"Rule Fired:                  {rule_fired}")
    print("=" * 70)
    print()

    return {
        "file": path.name,
        "format": path.suffix.lower(),
        "codec_class": codec_class,
        "is_lossy": is_lossy,
        "duration": duration_sec,
        "windows": len(windows),
        "speech_windows": metrics.get("speech_windows_count") if metrics else 0,
        "median": median_logit,
        "min": min_logit,
        "fraction_low": fraction_low,
        "longest_low_run": longest_low_run,
        "rule_fired": rule_fired,
        "verdict": verdict,
        "confidence": confidence,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/debug_scores.py <audio_file_1> [audio_file_2 ...]")
        sys.exit(1)
    for audio_arg in sys.argv[1:]:
        debug_file(audio_arg)

