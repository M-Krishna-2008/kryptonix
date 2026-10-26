from __future__ import annotations
import datetime
import hashlib
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

from .config import (
    MODULE_DIR,
    ARTIFACT_DIR,
    XLSR_MODEL_PATH,
    AASIST_MODEL_PATH,
    SCORE_DIRECTION,
    RAW_METRIC_NAME,
    load_thresholds,
)
from .schemas import (
    AnalysisResult,
    EvidenceFile,
    Finding,
    FindingLocation,
)
from .audio_preprocess import preprocess_and_window
from .model_aasist import (
    check_models_available,
    score_windows,
    get_torch_device,
)
from .heuristics import run_all_heuristics
from .visualizer import generate_visual_artifacts


def compute_sha256(file_path: str | Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_file_hash(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return compute_sha256(path)[:16]


def calculate_verdict_and_confidence(
    logits: np.ndarray,
    window_meta: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
    duration_sec: float,
    is_silent: bool,
    model_installed: bool,
    is_lossy: bool = False,
) -> tuple[str, float, Optional[Dict[str, Any]], List[Finding]]:
    """
    Evaluates verdicts strictly adhering to Steps 2, 3, 4, 5:
      - Speech-only VAD: windows with <50% speech are excluded from verdict scoring.
      - If fewer than 2 speech windows remain -> "inconclusive" ("not enough speech").
      - Partial tampering: at least 2 consecutive low windows (>= 6s run) AND
        at least 3 low windows in total AND fraction_low >= 0.25 AND >= 5 speech windows.
      - Whole clip tampering: median logit <= low_threshold AND fraction_low >= 0.60
        AND at least 3 speech windows.
      - Evidence near a threshold (borderline) defaults to "suspicious" or "inconclusive".
      - Clips with fewer than 3 windows can only be authentic, suspicious or inconclusive.
      - Heuristics cannot drive the verdict.
      - Lossy input caps confidence at medium (0.70).
    """
    findings: List[Finding] = []
    low_thresh = float(thresholds["low_threshold"])
    high_thresh = float(thresholds["high_threshold"])
    borderline_margin = float(thresholds.get("borderline_margin", 0.5))
    suspicious_margin = float(thresholds.get("suspicious_margin", 0.5))

    whole_clip_fraction_low = float(thresholds.get("whole_clip_fraction_low", thresholds.get("fraction_low_clip", 0.60)))
    whole_clip_min_windows = int(thresholds.get("whole_clip_min_windows", 3))

    partial_min_consecutive = int(thresholds.get("partial_min_consecutive_low", 2))
    partial_min_low = int(thresholds.get("partial_min_low_windows", 3))
    partial_min_fraction = float(thresholds.get("partial_min_fraction_low", thresholds.get("fraction_low_segment", 0.25)))
    partial_min_total_windows = int(thresholds.get("partial_min_total_windows", 5))
    min_run_s = float(thresholds.get("min_run_seconds", 6.0))

    fraction_low_auth = float(thresholds.get("fraction_low_authentic", 0.05))
    vad_min_speech_windows = int(thresholds.get("vad_min_speech_windows", 2))
    lossy_confidence_cap = float(thresholds.get("lossy_confidence_cap", 0.70))

    if not model_installed:
        findings.append(
            Finding(
                id="model_not_installed",
                check="model_not_installed",
                severity="high",
                confidence=1.0,
                description=(
                    "W2V2-AASIST model weights are not installed in audio_forensics/models/. "
                    "Deepfake speech verification cannot run. Run run_platform.bat or download "
                    "xlsr2_300m.pt and LA_model.pth into audio_forensics/models/ to enable neural scoring."
                ),
            )
        )
        return "inconclusive", 0.0, None, findings

    # Check for empty or silent recording
    if len(logits) < 1 or is_silent:
        return "inconclusive", 0.0, None, findings

    # Step 3: Speech-only scoring (VAD gating)
    speech_indices = [i for i, m in enumerate(window_meta) if m.get("has_speech", True)]
    
    # If fewer than 2 speech windows remain, return inconclusive with finding
    if len(speech_indices) < vad_min_speech_windows:
        findings.append(
            Finding(
                id="not_enough_speech",
                check="voice_activity_detection",
                severity="info",
                confidence=1.0,
                description=(
                    f"Recording contains insufficient speech activity ({len(speech_indices)} speech window(s) detected, "
                    f"minimum {vad_min_speech_windows} required). Windows with less than 50% speech are excluded from verdict scoring."
                ),
            )
        )
        summary_metrics = {
            "median_logit": None,
            "min_logit": None,
            "fraction_low": 0.0,
            "longest_low_run_s": 0.0,
            "longest_low_run_range": None,
            "speech_windows_count": len(speech_indices),
            "total_windows_count": len(window_meta),
        }
        return "inconclusive", 0.30, summary_metrics, findings

    speech_logits = logits[speech_indices]
    speech_meta = [window_meta[i] for i in speech_indices]
    n_speech = len(speech_logits)

    median_logit = float(np.median(speech_logits))
    min_logit = float(np.min(speech_logits))
    low_mask = speech_logits <= low_thresh
    num_low = int(np.sum(low_mask))
    fraction_low = float(np.mean(low_mask))

    # Calculate contiguous run of low windows among speech windows
    longest_run_s = 0.0
    current_run_s = 0.0
    best_range: Optional[List[float]] = None
    cur_start_sec = 0.0
    consecutive_low = 0
    max_consecutive_low = 0

    for idx, is_low in enumerate(low_mask):
        w_meta = speech_meta[idx]
        if is_low:
            consecutive_low += 1
            if consecutive_low > max_consecutive_low:
                max_consecutive_low = consecutive_low
            if current_run_s == 0.0:
                cur_start_sec = w_meta["start_sec"]
            current_run_s = w_meta["end_sec"] - cur_start_sec
            if current_run_s > longest_run_s:
                longest_run_s = current_run_s
                best_range = [round(cur_start_sec, 2), round(w_meta["end_sec"], 2)]
        else:
            consecutive_low = 0
            current_run_s = 0.0

    summary_metrics = {
        "median_logit": round(median_logit, 3),
        "min_logit": round(min_logit, 3),
        "fraction_low": round(fraction_low, 3),
        "longest_low_run_s": round(longest_run_s, 2),
        "longest_low_run_range": best_range,
        "max_consecutive_low": max_consecutive_low,
        "total_low_windows": num_low,
        "speech_windows_count": n_speech,
        "total_windows_count": len(window_meta),
    }

    # Add clip score finding
    findings.append(
        Finding(
            id="w2v2_aasist_clip",
            check="w2v2_aasist_clip_score",
            severity="info" if median_logit >= high_thresh else ("high" if median_logit <= low_thresh else "medium"),
            confidence=round(min(1.0, abs(median_logit) / 3.0), 2),
            description=(
                f"W2V2-AASIST neural detector yielded a median bona-fide score of {median_logit:.2f} "
                f"(range: [{min_logit:.2f}, {np.max(speech_logits):.2f}], threshold band: [{low_thresh:.1f}, {high_thresh:.1f}] across {n_speech} speech windows). "
                f"{fraction_low * 100:.1f}% of analyzed speech windows scored in the synthetic domain."
            ),
        )
    )

    verdict = "inconclusive"
    confidence = 0.50

    # Step 2 & Step 4: Verdict Decision Rules
    # Rule (b): Whole recording looks synthetic
    # Requires median_logit <= low_thresh AND fraction_low >= 0.60 AND at least 3 speech windows
    if n_speech >= whole_clip_min_windows and median_logit <= low_thresh and fraction_low >= whole_clip_fraction_low:
        # Default to inconclusive / suspicious whenever evidence is borderline
        if median_logit > (low_thresh - borderline_margin):
            verdict = "suspicious"
            confidence = 0.60
        else:
            verdict = "likely_tampered"
            dist = abs(low_thresh - median_logit)
            confidence = min(0.98, max(0.65, 0.60 + 0.15 * dist + 0.20 * fraction_low))
            findings.append(
                Finding(
                    id="synthetic_speech_entire",
                    check="synthetic_speech_segment",
                    severity="high",
                    confidence=round(confidence, 2),
                    description=(
                        f"The entire recording exhibits prominent synthetic / AI-generated voice characteristics. "
                        f"Median score ({median_logit:.2f}) is well below the synthetic threshold ({low_thresh:.1f}) "
                        f"with {fraction_low * 100:.1f}% of windows classified as synthetic."
                    ),
                    location=FindingLocation(time_range_sec=[0.0, round(duration_sec, 2)]),
                )
            )

    # Rule (c): Partial / spliced tampering
    # Requires at least 2 CONSECUTIVE low windows (run >= 6s) AND at least 3 low windows in total
    # AND fraction_low >= 0.25 AND at least 5 windows.
    elif (
        n_speech >= partial_min_total_windows
        and max_consecutive_low >= partial_min_consecutive
        and num_low >= partial_min_low
        and fraction_low >= partial_min_fraction
        and longest_run_s >= min_run_s
    ):
        verdict = "likely_tampered"
        confidence = min(0.92, max(0.60, 0.55 + 0.05 * longest_run_s + 0.15 * fraction_low))
        findings.append(
            Finding(
                id="synthetic_speech_segment_splice",
                check="synthetic_speech_segment",
                severity="high",
                confidence=round(confidence, 2),
                description=(
                    f"Between {best_range[0] if best_range else 0.0} s and {best_range[1] if best_range else duration_sec} s "
                    f"({max_consecutive_low} consecutive speech windows, {longest_run_s:.1f} s run) "
                    "the voice exhibits synthetic characteristics, while the rest looks natural. "
                    "This may be an inserted, spliced, or synthesized speech segment."
                ),
                location=FindingLocation(time_range_sec=best_range),
            )
        )

    # Rule (d): Authentic
    elif median_logit >= high_thresh and fraction_low <= fraction_low_auth:
        verdict = "authentic"
        dist = abs(median_logit - high_thresh)
        confidence = min(0.95, max(0.65, 0.60 + 0.10 * dist + (1.0 - fraction_low) * 0.20))

    # Rule (e): Suspicious or inconclusive
    else:
        if (high_thresh - suspicious_margin) <= median_logit < high_thresh:
            verdict = "suspicious"
            confidence = 0.55
        elif low_thresh < median_logit <= (low_thresh + suspicious_margin):
            verdict = "suspicious"
            confidence = 0.60
        elif median_logit <= low_thresh:
            # Below low threshold but failed whole-clip criteria (e.g. <3 windows or borderline fraction)
            verdict = "suspicious"
            confidence = 0.60
        else:
            verdict = "inconclusive"
            confidence = 0.45

    # Safety constraint: Clips with fewer than 3 speech windows can never be "likely_tampered"
    if n_speech < 3 and verdict.startswith("likely_tampered"):
        verdict = "suspicious" if median_logit <= low_thresh else "inconclusive"

    # Codec awareness confidence cap (Step 4)
    if is_lossy:
        confidence = min(confidence, lossy_confidence_cap)

    # Short clip confidence cap
    if duration_sec < 4.5:
        confidence = min(confidence, 0.70)

    return verdict, round(confidence, 2), summary_metrics, findings


def analyze(file_path: str, options: dict | None = None) -> dict:
    """
    Core entry point for audio forensics module.
    Adheres strictly to the Standard Result Format. Never raises to caller.
    """
    start_time = time.time()
    errors: List[str] = []
    findings: List[Finding] = []
    path = Path(file_path)

    # 1. File verification & metadata
    if not path.is_file():
        return {
            "module": "audio_forensics",
            "version": "1.0",
            "evidence_file": {"name": path.name, "sha256": "", "size_bytes": 0, "type": "unknown"},
            "analyzed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": str(ARTIFACT_DIR.relative_to(MODULE_DIR.parent)),
            "errors": [f"File not found: {file_path}"],
            "raw_metrics": {},
        }

    file_size = path.stat().st_size
    file_sha256 = compute_sha256(path)
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "audio/octet-stream"

    orig_name = options.get("original_filename") if options else None
    evidence_name = orig_name or path.name

    evidence_info = {
        "name": evidence_name,
        "sha256": file_sha256,
        "size_bytes": file_size,
        "type": mime_type,
    }

    # 2. Standing Countermeasure Notice (Mandatory standard info finding)
    findings.append(
        Finding(
            id="standing_countermeasure_notice",
            check="standing_notice",
            severity="info",
            confidence=1.0,
            description=(
                "This detector is a countermeasure. It does not identify the speaker, "
                "prove consent, or prove who created the audio. Accuracy drops on codecs, "
                "languages, noise and generators not seen in training. It is one signal; corroborate."
            ),
        )
    )

    # 3. Preprocessing, Codec Detection & Windowing
    pre_res = preprocess_and_window(path)
    if pre_res["errors"]:
        errors.extend(pre_res["errors"])

    y = pre_res["waveform"]
    sr = pre_res["sample_rate"]
    windows = pre_res["windows"]
    window_meta = pre_res["window_meta"]
    flags = pre_res["flags"]
    duration_sec = pre_res["duration_sec"]
    codec_info = pre_res.get("codec_info", {})
    codec_class = codec_info.get("codec_class", "lossless")
    is_lossy = codec_info.get("is_lossy", False)

    # Add codec awareness finding (Step 4)
    if is_lossy:
        codec_name = codec_info.get("codec", "compressed")
        bitrate_kbps = codec_info.get("bitrate_kbps")
        br_str = f", ~{bitrate_kbps} kbps" if bitrate_kbps else ""
        findings.append(
            Finding(
                id="lossy_codec_input",
                check="lossy_codec_input",
                severity="info",
                confidence=1.0,
                description=(
                    f"Input audio uses lossy compression ({codec_name}{br_str}). "
                    "Compression artifacts can degrade acoustic features and make genuine human speech appear synthetic. "
                    f"Applied widened uncertain band ({codec_class} thresholds) and capped confidence at medium."
                ),
            )
        )

    # Report VAD excluded non-speech windows (Step 3)
    non_sp_count = flags.get("non_speech_windows_count", 0)
    if non_sp_count > 0:
        findings.append(
            Finding(
                id="vad_non_speech_excluded",
                check="voice_activity_detection",
                severity="info",
                confidence=1.0,
                description=(
                    f"{non_sp_count} window(s) contained less than 50% speech activity (silence, noise, or music) "
                    "and were excluded from verdict calculation (marked as 'no speech' on the timeline)."
                ),
            )
        )

    if flags.get("short_clip_padded"):
        findings.append(
            Finding(
                id="short_clip_padded_1",
                check="short_clip_padded",
                severity="low",
                confidence=1.0,
                description=(
                    f"Recording length ({duration_sec:.2f} s) is shorter than the 4.04-second model window. "
                    "Waveform was cyclically tiled to reach 64,600 samples for inference."
                ),
                location=FindingLocation(time_range_sec=[0.0, duration_sec]),
            )
        )

    # 4. Model Scoring & Thresholds
    thresholds = load_thresholds(codec_class=codec_class)
    model_installed, missing_files = check_models_available()

    logits = np.zeros(0, dtype=np.float32)
    inference_ms = 0.0

    if model_installed and len(windows) > 0 and not flags.get("is_silent"):
        t_inf_start = time.time()
        logits, score_err = score_windows(windows)
        inference_ms = round((time.time() - t_inf_start) * 1000.0, 1)
        if score_err:
            errors.append(score_err)

    # 5. Verdict & Summary Metrics
    verdict, confidence, summary_metrics, model_findings = calculate_verdict_and_confidence(
        logits=logits,
        window_meta=window_meta,
        thresholds=thresholds,
        duration_sec=duration_sec,
        is_silent=flags.get("is_silent", False),
        model_installed=model_installed,
        is_lossy=is_lossy,
    )
    findings.extend(model_findings)

    # 6. Heuristic Checks (Edit / Splice detection)
    # Heuristics can NEVER by themselves set the verdict to "likely_tampered"
    change_points: List[float] = []
    raw_heuristics = {}
    if len(y) > 0:
        h_findings, raw_heuristics = run_all_heuristics(
            file_path=str(path),
            y=y,
            sr=sr,
            short_clip_padded=flags.get("short_clip_padded", False),
        )
        findings.extend(h_findings)
        # Extract change points for spectrogram marker
        for hf in h_findings:
            if hf.location and hf.location.time_range_sec:
                change_points.append(hf.location.time_range_sec[0])

    # 7. Generate Visual Artifacts
    sha_prefix = file_sha256[:12]
    art_map = generate_visual_artifacts(
        y=y,
        sr=sr,
        window_meta=window_meta,
        logits=logits,
        low_thresh=thresholds["low_threshold"],
        high_thresh=thresholds["high_threshold"],
        change_points=change_points,
        artifacts_dir=ARTIFACT_DIR,
        sha256_prefix=sha_prefix,
    )


    # Attach visual artifacts to findings
    for f in findings:
        if f.check in ("w2v2_aasist_clip_score", "synthetic_speech_segment"):
            f.evidence_artifacts = [art_map.get("waveform", ""), art_map.get("timeline", "")]
        elif f.check in ("noise_floor_jump", "spectral_discontinuity", "bandwidth_inconsistency"):
            f.evidence_artifacts = [art_map.get("spectrogram", ""), art_map.get("waveform", "")]

    # Sort findings by severity (high -> medium -> low -> info)
    sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda x: sev_rank.get(x.severity, 4))

    # Package raw_metrics
    device_str = str(get_torch_device())
    raw_metrics: Dict[str, Any] = {
        "score_direction": SCORE_DIRECTION,
        "raw_metric_name": RAW_METRIC_NAME,
        "thresholds_used": thresholds,
        "clip_summary": summary_metrics or {},
        "windows_analyzed": len(windows),
        "per_window_logits": [
            {
                "window_idx": m["index"],
                "start_sec": m["start_sec"],
                "end_sec": m["end_sec"],
                "has_speech": m.get("has_speech", True),
                "speech_ratio": m.get("speech_ratio", 1.0),
                "bona_fide_logit": round(float(logits[i]), 4) if i < len(logits) else None,
            }
            for i, m in enumerate(window_meta)
        ],
        "heuristics": raw_heuristics,
        "audio_info": {
            "duration_sec": duration_sec,
            "orig_sr": pre_res.get("orig_sr", sr),
            "proc_sr": sr,
            "rms_energy": flags.get("rms", 0.0),
            "peak_amplitude": flags.get("peak", 0.0),
        },
        "model_info": {
            "model_installed": model_installed,
            "xlsr_hash": compute_file_hash(XLSR_MODEL_PATH),
            "aasist_hash": compute_file_hash(AASIST_MODEL_PATH),
            "device": device_str,
            "inference_ms": inference_ms,
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "torch_version": getattr(sys.modules.get("torch"), "__version__", "not_loaded"),
        },
        "visual_artifacts": art_map,
        "total_elapsed_ms": round((time.time() - start_time) * 1000.0, 1),
    }

    try:
        import fairseq
        raw_metrics["environment"]["fairseq_version"] = getattr(fairseq, "__version__", "unknown")
    except Exception:
        pass

    try:
        relative_artifacts_dir = str(ARTIFACT_DIR.relative_to(MODULE_DIR.parent)).replace("\\", "/")
    except Exception:
        relative_artifacts_dir = str(ARTIFACT_DIR).replace("\\", "/")

    result_dict = {
        "module": "audio_forensics",
        "version": "1.0",
        "evidence_file": evidence_info,
        "analyzed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "overall_confidence": confidence,
        "findings": [f.model_dump() if hasattr(f, "model_dump") else f.dict() for f in findings],
        "artifacts_dir": relative_artifacts_dir,
        "errors": errors,
        "raw_metrics": raw_metrics,
    }

    return result_dict
