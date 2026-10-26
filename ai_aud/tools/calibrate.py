#!/usr/bin/env python3
"""
tools/calibrate.py

Comprehensive Calibration Engine for W2V2-AASIST Audio Forensics:
- Accepts genuine and spoof audio directories.
- Tests across formats: original, mp3 128 kbps, mp3 64 kbps.
- Computes per-format EER, AUC, and score distribution (min, median, max).
- Sets low_threshold at 2% false accusation rate (FAR) on genuine audio.
- Writes per-codec-class thresholds to audio_forensics/configs/thresholds.yaml.
- Prints false-positive rate and detection rate for each format.
- Emits explicit warning if AUC < 0.80.
"""

from __future__ import annotations
import argparse
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import yaml
import av

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from audio_forensics.config import CONFIGS_DIR, load_thresholds
from audio_forensics.analyzer import analyze


def convert_audio_to_mp3(src_path: Path, dst_path: Path, bitrate_kbps: int) -> Path:
    """Encodes input audio to MP3 at specified bitrate using PyAV."""
    if dst_path.is_file() and dst_path.stat().st_size > 0:
        return dst_path

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    in_container = av.open(str(src_path))
    audio_streams = [s for s in in_container.streams if s.type == "audio"]
    if not audio_streams:
        in_container.close()
        raise ValueError(f"No audio stream in {src_path.name}")

    in_stream = audio_streams[0]
    sample_rate = in_stream.rate or 16000

    out_container = av.open(str(dst_path), mode="w", format="mp3")
    out_stream = out_container.add_stream("mp3", rate=sample_rate)
    out_stream.bit_rate = bitrate_kbps * 1000

    resampler = av.AudioResampler(
        format="s16p",
        layout="mono",
        rate=sample_rate,
    )

    for frame in in_container.decode(in_stream):
        for rf in resampler.resample(frame):
            for packet in out_stream.encode(rf):
                out_container.mux(packet)

    for packet in out_stream.encode():
        out_container.mux(packet)

    out_container.close()
    in_container.close()
    return dst_path


def score_files(files: List[Path]) -> List[float]:
    """Runs audio forensics analyzer and extracts median logit for each file."""
    scores = []
    for f in files:
        try:
            print(f"    Scoring {f.name}...", flush=True)
            res = analyze(str(f))
            clip_summary = res.get("raw_metrics", {}).get("clip_summary", {})
            med = clip_summary.get("median_logit")
            if med is not None:
                scores.append(float(med))
            else:
                # Fallback to direct window scoring if VAD excluded or empty
                logits = [w["bona_fide_logit"] for w in res.get("raw_metrics", {}).get("per_window_logits", []) if w.get("bona_fide_logit") is not None]
                if logits:
                    scores.append(float(np.median(logits)))
        except Exception as e:
            print(f"  [ERROR] Scoring {f.name}: {e}", flush=True)
    return scores



def compute_metrics_and_thresholds(
    genuine_scores: np.ndarray,
    spoof_scores: np.ndarray,
    target_genuine_far: float = 0.02,
) -> Dict[str, float]:
    """
    Computes ROC-AUC, EER, and sets low_threshold so false-accusation rate
    on genuine audio is target_genuine_far (2%).
    """
    if len(genuine_scores) == 0 or len(spoof_scores) == 0:
        raise ValueError("Must have at least one score in both genuine and spoof sets.")

    y_true = np.concatenate([np.ones(len(genuine_scores)), np.zeros(len(spoof_scores))])
    y_scores = np.concatenate([genuine_scores, spoof_scores])

    # Sort descending
    sort_idx = np.argsort(-y_scores)
    y_true_sorted = y_true[sort_idx]
    y_scores_sorted = y_scores[sort_idx]

    n_pos = len(genuine_scores)
    n_neg = len(spoof_scores)

    tps = np.cumsum(y_true_sorted)
    fps = np.cumsum(1.0 - y_true_sorted)

    fpr = fps / n_neg
    tpr = tps / n_pos
    fnr = 1.0 - tpr

    # Trapezoidal ROC-AUC
    auc = float(np.trapz(tpr, fpr)) if len(fpr) > 1 else 1.0

    # EER
    diff = np.abs(fpr - fnr)
    min_idx = int(np.argmin(diff))
    eer = float((fpr[min_idx] + fnr[min_idx]) / 2.0)
    eer_thresh = float(y_scores_sorted[min_idx])

    # Target: 2% False Accusation Rate on genuine audio (Bona-fide classified as spoof)
    # A genuine file is falsely accused if logit < low_threshold.
    # Therefore, low_threshold is the 2nd percentile of genuine scores.
    if len(genuine_scores) == 1:
        low_thresh = float(genuine_scores[0] - 0.5)
    else:
        low_thresh = float(np.percentile(genuine_scores, target_genuine_far * 100.0))

    # Evaluate empirical FPR on genuine audio and Detection Rate on spoof audio
    actual_far_genuine = float(np.mean(genuine_scores < low_thresh))
    detection_rate_spoof = float(np.mean(spoof_scores <= low_thresh))

    # High threshold (e.g. 95% genuine pass point or EER+1)
    high_thresh = max(1.5, float(np.percentile(genuine_scores, 15.0)))

    return {
        "auc": auc,
        "eer": eer,
        "eer_threshold": eer_thresh,
        "low_threshold": low_thresh,
        "high_threshold": high_thresh,
        "false_accusation_rate": actual_far_genuine,
        "detection_rate": detection_rate_spoof,
    }


def calibrate_datasets(
    genuine_dir: str | Path,
    spoof_dir: str | Path,
    save_yaml: bool = True,
) -> Dict[str, Any]:
    g_path = Path(genuine_dir)
    s_path = Path(spoof_dir)

    if not g_path.is_dir() or not s_path.is_dir():
        print(f"[ERROR] Directories do not exist:\n  Genuine: {g_path}\n  Spoof: {s_path}")
        return {}

    audio_exts = {".wav", ".flac", ".mp3", ".ogg", ".aac", ".m4a"}
    g_files = [f for f in g_path.iterdir() if f.is_file() and f.suffix.lower() in audio_exts]
    s_files = [f for f in s_path.iterdir() if f.is_file() and f.suffix.lower() in audio_exts]

    if not g_files or not s_files:
        print(f"[ERROR] No audio files found in directories (genuine: {len(g_files)}, spoof: {len(s_files)})")
        return {}

    print("=" * 75)
    print("PS-05 Audio Forensics Calibration on Domain Data")
    print(f"Genuine audio directory: {g_path} ({len(g_files)} files)")
    print(f"Spoof audio directory:   {s_path} ({len(s_files)} files)")
    print("=" * 75)

    tmp_dir = PROJECT_ROOT / "cache" / "calibration_converted"
    (tmp_dir / "genuine").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "spoof").mkdir(parents=True, exist_ok=True)

    formats = ["original", "mp3_128k", "mp3_64k"]
    results_per_format = {}

    for fmt in formats:
        print(f"\nEvaluating format: {fmt} ...")
        if fmt == "original":
            cur_g = g_files
            cur_s = s_files
        elif fmt == "mp3_128k":
            cur_g = [convert_audio_to_mp3(f, tmp_dir / "genuine" / f"{f.stem}_128k.mp3", 128) for f in g_files]
            cur_s = [convert_audio_to_mp3(f, tmp_dir / "spoof" / f"{f.stem}_128k.mp3", 128) for f in s_files]
        else:  # mp3_64k
            cur_g = [convert_audio_to_mp3(f, tmp_dir / "genuine" / f"{f.stem}_64k.mp3", 64) for f in g_files]
            cur_s = [convert_audio_to_mp3(f, tmp_dir / "spoof" / f"{f.stem}_64k.mp3", 64) for f in s_files]

        g_scores = np.array(score_files(cur_g), dtype=np.float32)
        s_scores = np.array(score_files(cur_s), dtype=np.float32)

        if len(g_scores) == 0 or len(s_scores) == 0:
            print(f"[WARN] No scores obtained for format {fmt}")
            continue

        metrics = compute_metrics_and_thresholds(g_scores, s_scores, target_genuine_far=0.02)
        metrics["g_min"] = float(np.min(g_scores))
        metrics["g_med"] = float(np.median(g_scores))
        metrics["g_max"] = float(np.max(g_scores))
        metrics["s_min"] = float(np.min(s_scores))
        metrics["s_med"] = float(np.median(s_scores))
        metrics["s_max"] = float(np.max(s_scores))

        results_per_format[fmt] = metrics

        print(f"  Genuine Logit distribution: min={metrics['g_min']:.2f}, median={metrics['g_med']:.2f}, max={metrics['g_max']:.2f}")
        print(f"  Spoof Logit distribution:   min={metrics['s_min']:.2f}, median={metrics['s_med']:.2f}, max={metrics['s_max']:.2f}")
        print(f"  ROC-AUC:                    {metrics['auc']:.4f}")
        print(f"  Equal Error Rate (EER):     {metrics['eer'] * 100:.2f}% (EER thresh: {metrics['eer_threshold']:.2f})")
        print(f"  Calibrated low_threshold:   {metrics['low_threshold']:.2f} (Target genuine FAR: 2.0%)")
        print(f"  Actual False-Accusation Rt: {metrics['false_accusation_rate'] * 100:.2f}% on genuine")
        print(f"  Spoof Detection Rate:       {metrics['detection_rate'] * 100:.2f}% on spoof")

        if metrics["auc"] < 0.80:
            print("\n  [WARNING] AUC is below 0.80 on your data!")
            print("  This model does not separate your genuine and synthetic audio well.")
            print("  Consider domain adaptation (fine-tuning on representative data) or using this module only as a weak signal.\n")

    # Construct calibrated thresholds.yaml
    out_file = CONFIGS_DIR / "thresholds.yaml"

    lossless_res = results_per_format.get("original", {})
    lossy_128_res = results_per_format.get("mp3_128k", {})
    lossy_64_res = results_per_format.get("mp3_64k", {})

    # Safety bounds to prevent unrealistic over-fitting on small sample sizes
    t_lossless_low = round(min(-1.5, lossless_res.get("low_threshold", -1.5)), 2)
    t_lossy_high_low = round(min(-2.0, lossy_128_res.get("low_threshold", -2.5)), 2)
    t_lossy_low_low = round(min(-3.0, lossy_64_res.get("low_threshold", -4.5)), 2)

    calib_data = {
        "thresholds": {
            "low_threshold": t_lossy_high_low,
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
            "codec_classes": {
                "lossless": {
                    "low_threshold": t_lossless_low,
                    "high_threshold": 1.5,
                    "borderline_margin": 0.5,
                    "lossy_margin": 0.0,
                },
                "lossy_high_bitrate": {
                    "low_threshold": t_lossy_high_low,
                    "high_threshold": 1.5,
                    "borderline_margin": 0.75,
                    "lossy_margin": 1.0,
                },
                "lossy_low_bitrate": {
                    "low_threshold": t_lossy_low_low,
                    "high_threshold": 1.5,
                    "borderline_margin": 1.0,
                    "lossy_margin": 2.0,
                },
            },
        },
        "calibration_metadata": {
            "calibrated": True,
            "target_far_percent": 2.0,
            "genuine_dir": str(g_path),
            "spoof_dir": str(s_path),
            "formats_evaluated": results_per_format,
        },
    }

    if save_yaml:
        with open(out_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(calib_data, f, sort_keys=False)
        print(f"\n[SUCCESS] Calibrated per-codec thresholds saved to {out_file}")

    return results_per_format


def main():
    parser = argparse.ArgumentParser(description="Calibrate PS-05 Audio Forensics decision thresholds on genuine and spoof audio.")
    parser.add_argument("genuine_dir", type=str, nargs="?", default="data_audio/bonafide", help="Path to directory containing genuine audio files.")
    parser.add_argument("spoof_dir", type=str, nargs="?", default="data_audio/spoof", help="Path to directory containing spoof / synthetic audio files.")
    parser.add_argument("--save", dest="save_yaml", action="store_true", default=True, help="Write calibrated thresholds to thresholds.yaml (default)")
    parser.add_argument("--no-save", dest="save_yaml", action="store_false", help="Do not write results to thresholds.yaml")
    args = parser.parse_args()

    g_dir = Path(args.genuine_dir)
    s_dir = Path(args.spoof_dir)

    # Fallback if specified directories do not exist
    if not g_dir.is_dir() or not s_dir.is_dir():
        diag_dir = PROJECT_ROOT / "data_diagnosis"
        if diag_dir.is_dir():
            print(f"[INFO] '{g_dir}' or '{s_dir}' not found. Using '{diag_dir}' as sample source.")
            g_dir = diag_dir
            s_dir = diag_dir

    if g_dir == s_dir and g_dir.name == "data_diagnosis":
        # Separate genuine and tts files into dedicated subfolders for clean scoring
        temp_g = PROJECT_ROOT / "cache" / "calib_genuine"
        temp_s = PROJECT_ROOT / "cache" / "calib_spoof"
        temp_g.mkdir(parents=True, exist_ok=True)
        temp_s.mkdir(parents=True, exist_ok=True)

        import shutil
        for f in g_dir.glob("genuine_*.flac"):
            shutil.copy(f, temp_g / f.name)

        for f in g_dir.glob("tts_*.wav"):
            shutil.copy(f, temp_s / f.name)

        calibrate_datasets(temp_g, temp_s, save_yaml=args.save_yaml)
    else:
        calibrate_datasets(g_dir, s_dir, save_yaml=args.save_yaml)


if __name__ == "__main__":
    main()
