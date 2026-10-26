from __future__ import annotations
import math
from typing import List, Dict, Any, Tuple
import numpy as np

from .schemas import Finding, FindingLocation


def detect_noise_floor_jump(
    y: np.ndarray,
    sr: int = 16000,
    frame_len_sec: float = 1.0,
    hop_sec: float = 0.5,
    jump_threshold_db: float = 12.0,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Heuristic check: Abrupt change in background noise level between adjacent segments.
    Estimates the 10th percentile energy in sliding windows.
    """
    findings: List[Finding] = []
    frame_samples = int(frame_len_sec * sr)
    hop_samples = int(hop_sec * sr)
    total_samples = len(y)

    if total_samples < frame_samples * 2:
        return findings, {"checked": False, "reason": "audio_too_short"}

    num_frames = (total_samples - frame_samples) // hop_samples + 1
    noise_db_levels: List[float] = []
    timestamps: List[float] = []

    sub_frame = sr // 20  # 50ms sub-windows

    for i in range(num_frames):
        start = i * hop_samples
        end = start + frame_samples
        window = y[start:end]
        # Calculate sub-window RMS energies to find the noise floor (10th percentile)
        n_subs = len(window) // sub_frame
        if n_subs < 2:
            sub_rms = [float(np.sqrt(np.mean(window**2) + 1e-12))]
        else:
            sub_rms = [
                float(np.sqrt(np.mean(window[j * sub_frame : (j + 1) * sub_frame] ** 2) + 1e-12))
                for j in range(n_subs)
            ]
        p10 = float(np.percentile(sub_rms, 10))
        db = 20.0 * math.log10(max(p10, 1e-6))
        noise_db_levels.append(db)
        timestamps.append(round(start / sr, 3))

    max_jump = 0.0
    jump_loc: float = 0.0

    for i in range(1, len(noise_db_levels)):
        diff = abs(noise_db_levels[i] - noise_db_levels[i - 1])
        if diff > max_jump:
            max_jump = diff
            jump_loc = timestamps[i]

        if diff >= jump_threshold_db:
            t_start = max(0.0, timestamps[i] - 0.5)
            t_end = min(round(total_samples / sr, 3), timestamps[i] + frame_len_sec)
            conf = min(0.95, round(diff / 25.0, 2))
            findings.append(
                Finding(
                    id=f"noise_jump_{i}",
                    check="noise_floor_jump",
                    severity="medium",
                    confidence=conf,
                    description=(
                        f"[HEURISTIC] Abrupt background noise jump of {diff:.1f} dB detected around {timestamps[i]:.2f} s. "
                        "This sudden step change may indicate a spliced or combined recording from different acoustic environments."
                    ),
                    location=FindingLocation(time_range_sec=[t_start, t_end]),
                )
            )

    metrics = {
        "checked": True,
        "max_noise_jump_db": round(max_jump, 2),
        "jump_location_sec": jump_loc,
        "noise_levels_sampled": len(noise_db_levels),
    }
    return findings, metrics


def detect_spectral_discontinuity(
    y: np.ndarray,
    sr: int = 16000,
    n_fft: int = 512,
    hop_length: int = 256,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Heuristic check: Sudden change points in spectrogram (spectral flux anomaly).
    """
    findings: List[Finding] = []
    total_samples = len(y)
    if total_samples < n_fft * 4:
        return findings, {"checked": False, "reason": "audio_too_short"}

    try:
        from scipy.signal import stft
        _, _, Zxx = stft(y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length)
        mag = np.abs(Zxx)
    except Exception:
        # Simple spectrogram fallback
        window = np.hanning(n_fft)
        num_frames = (total_samples - n_fft) // hop_length + 1
        mags = []
        for i in range(num_frames):
            seg = y[i * hop_length : i * hop_length + n_fft] * window
            mags.append(np.abs(np.fft.rfft(seg)))
        mag = np.array(mags).T if mags else np.zeros((n_fft // 2 + 1, 1))

    if mag.shape[1] < 5:
        return findings, {"checked": False, "reason": "insufficient_frames"}

    # Spectral flux: positive half-wave rectified Euclidean distance
    flux = np.sum(np.maximum(0, np.diff(mag, axis=1)) ** 2, axis=0)
    flux = np.sqrt(flux + 1e-12)

    mean_flux = float(np.mean(flux))
    std_flux = float(np.std(flux))
    thresh = mean_flux + 4.5 * std_flux

    peak_indices = np.where(flux > thresh)[0]
    clusters: List[List[int]] = []

    # Cluster peaks that are within 0.3s of each other
    hop_sec = hop_length / float(sr)
    for p in peak_indices:
        if not clusters or (p - clusters[-1][-1]) > int(0.3 / hop_sec):
            clusters.append([p])
        else:
            clusters[-1].append(p)

    # Calculate overall RMS to check for silence/pauses around change points
    overall_rms = float(np.sqrt(np.mean(y**2))) if total_samples > 0 else 0.0

    for idx, cl in enumerate(clusters):
        peak_frame = cl[int(np.argmax(flux[cl]))]
        t_center = peak_frame * hop_sec

        ratio = float(flux[peak_frame] / (mean_flux + 1e-6))
        # Require a minimum duration for change points unless prominent sharp discontinuity (ratio >= 5.0)
        cluster_dur = (cl[-1] - cl[0] + 1) * hop_sec
        if len(cl) < 2 and cluster_dur < 0.03 and ratio < 5.0:
            continue


        # Ignore spectral changes that coincide with silence / pauses
        s_samp = max(0, int((t_center - 0.15) * sr))
        e_samp = min(total_samples, int((t_center + 0.15) * sr))
        local_rms = float(np.sqrt(np.mean(y[s_samp:e_samp]**2))) if e_samp > s_samp else 0.0
        if local_rms < 0.005 or (overall_rms > 0 and local_rms < 0.12 * overall_rms):
            continue
        conf = min(0.85, round(ratio / 15.0, 2))
        findings.append(
            Finding(
                id=f"spectral_discont_{idx}",
                check="spectral_discontinuity",
                severity="low" if ratio < 8.0 else "medium",
                confidence=conf,
                description=(
                    f"[HEURISTIC] Significant spectral flux discontinuity ({ratio:.1f}x baseline) detected at {t_center:.2f} s. "
                    "May indicate an unnatural cut point, splice transient, or abrupt edit boundary."
                ),
                location=FindingLocation(time_range_sec=[max(0.0, t_center - 0.2), t_center + 0.2]),
            )
        )
        if len(findings) >= 5:
            break

    metrics = {
        "checked": True,
        "anomalous_flux_peaks": len(clusters),
        "mean_flux": round(mean_flux, 4),
        "std_flux": round(std_flux, 4),
    }
    return findings, metrics


def detect_repeated_segment(
    y: np.ndarray,
    sr: int = 16000,
    segment_sec: float = 1.0,
    step_sec: float = 0.5,
    short_clip_padded: bool = False,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Heuristic check: Copy-paste tampering detection via cross-correlation of segmented energy envelopes.
    Does not run on clips that were tiled/padded to reach model window.
    """
    findings: List[Finding] = []
    if short_clip_padded:
        return findings, {"checked": False, "reason": "short_clip_padded"}

    seg_samples = int(segment_sec * sr)
    step_samples = int(step_sec * sr)
    total_samples = len(y)

    # Need at least 4 seconds to meaningfully check for segment repetition
    if total_samples < sr * 4:
        return findings, {"checked": False, "reason": "audio_too_short_for_repetition"}

    # Extract downsampled energy envelopes (e.g. 100 Hz downsampled RMS envelope)
    env_step = sr // 100
    n_pts = total_samples // env_step
    envelope = np.array([
        float(np.sqrt(np.mean(y[i * env_step : (i + 1) * env_step] ** 2) + 1e-12))
        for i in range(n_pts)
    ])
    # Normalize envelope
    env_std = np.std(envelope)
    if env_std < 1e-4:
        return findings, {"checked": False, "reason": "flat_envelope"}
    envelope = (envelope - np.mean(envelope)) / env_std

    seg_pts = int(segment_sec * 100)
    step_pts = int(step_sec * 100)
    num_segs = (len(envelope) - seg_pts) // step_pts

    max_corr = 0.0
    match_pair = None

    # Compare non-adjacent segments (at least 2 seconds apart)
    min_dist_pts = int(2.0 * 100)
    for i in range(min(num_segs, 40)):
        s1 = envelope[i * step_pts : i * step_pts + seg_pts]
        norm1 = np.linalg.norm(s1)
        if norm1 < 1e-3:
            continue
        for j in range(i + (min_dist_pts // step_pts), min(num_segs, 40)):
            s2 = envelope[j * step_pts : j * step_pts + seg_pts]
            norm2 = np.linalg.norm(s2)
            if norm2 < 1e-3:
                continue
            corr = float(np.dot(s1, s2) / (norm1 * norm2))
            if corr > max_corr:
                max_corr = corr
                match_pair = (i * step_sec, j * step_sec)

            if corr >= 0.96:
                t1 = round(i * step_sec, 2)
                t2 = round(j * step_sec, 2)
                findings.append(
                    Finding(
                        id=f"repeat_{i}_{j}",
                        check="repeated_segment",
                        severity="medium",
                        confidence=min(0.90, round(corr, 2)),
                        description=(
                            f"[HEURISTIC] Nearly identical acoustic segment detected between {t1:.2f} s and {t1 + segment_sec:.2f} s, "
                            f"repeated at {t2:.2f} s (correlation {corr:.2f}). Possible copy-paste audio clone or inserted duplicate."
                        ),
                        location=FindingLocation(time_range_sec=[t1, t2 + segment_sec]),
                    )
                )
                break
        if findings:
            break

    metrics = {
        "checked": True,
        "max_segment_correlation": round(max_corr, 3),
        "best_match_locations": match_pair,
    }
    return findings, metrics


def detect_bandwidth_inconsistency(
    y: np.ndarray,
    sr: int = 16000,
    win_sec: float = 2.0,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Heuristic check: Spectral rolloff (effective cutoff frequency) inconsistency across sections.
    Detects if different segments have drastically different frequency cutoffs (e.g. 4kHz vs 8kHz).
    """
    findings: List[Finding] = []
    total_samples = len(y)
    win_samples = int(win_sec * sr)
    if total_samples < win_samples * 2:
        return findings, {"checked": False, "reason": "audio_too_short"}

    n_wins = total_samples // win_samples
    rolloffs: List[float] = []

    for i in range(n_wins):
        seg = y[i * win_samples : (i + 1) * win_samples]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        power = spec**2
        total_p = np.sum(power)
        if total_p < 1e-8:
            continue
        cum_p = np.cumsum(power)
        # 85% spectral rolloff frequency
        cutoff_idx = np.searchsorted(cum_p, 0.85 * total_p)
        freq = (cutoff_idx / float(len(spec))) * (sr / 2.0)
        rolloffs.append(freq)

    if len(rolloffs) < 2:
        return findings, {"checked": False, "reason": "insufficient_segments"}

    min_cut = float(np.min(rolloffs))
    max_cut = float(np.max(rolloffs))
    delta_hz = max_cut - min_cut

    if delta_hz >= 2500.0:
        findings.append(
            Finding(
                id="bandwidth_inconsistent_1",
                check="bandwidth_inconsistency",
                severity="medium",
                confidence=min(0.85, round(delta_hz / 4000.0, 2)),
                description=(
                    f"[HEURISTIC] Inconsistent frequency bandwidth detected across segments (range: {min_cut:.0f} Hz to {max_cut:.0f} Hz, "
                    f"delta: {delta_hz:.0f} Hz). Suggests composite audio spliced from sources with different sample rates or codecs."
                ),
                location=FindingLocation(time_range_sec=[0.0, round(total_samples / sr, 2)]),
            )
        )

    metrics = {
        "checked": True,
        "min_rolloff_hz": round(min_cut, 1),
        "max_rolloff_hz": round(max_cut, 1),
        "delta_hz": round(delta_hz, 1),
    }
    return findings, metrics


def inspect_metadata_flags(file_path: str) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Checks container tags for editing software (Audacity, FFmpeg, Adobe Audition, ElevenLabs, etc.)
    or timestamp anomalies.
    """
    findings: List[Finding] = []
    tags_found: Dict[str, str] = {}
    suspicious_tools = [
        "audacity", "adobe", "audition", "ffmpeg", "elevenlabs", "sox",
        "soundforge", "protools", "logic", "flstudio", "cubase", "goldwave",
        "tortoise", "bark", "vits", "piper", "coqui"
    ]

    try:
        import mutagen
        meta = mutagen.File(file_path)
        if meta and hasattr(meta, "tags") and meta.tags:
            for k, v in meta.tags.items():
                val_str = str(v)
                tags_found[str(k)] = val_str
                val_lower = val_str.lower()
                for tool in suspicious_tools:
                    if tool in val_lower:
                        findings.append(
                            Finding(
                                id=f"meta_software_{k}",
                                check="metadata_flags",
                                severity="low",
                                confidence=0.75,
                                description=(
                                    f"[HEURISTIC] Metadata tag '{k}' contains '{tool}' signature ('{val_str}'). "
                                    "Indicates audio post-processing or synthesis software was utilized."
                                ),
                                location=FindingLocation(metadata_field=str(k)),
                            )
                        )
                        break
    except Exception as e:
        tags_found["read_error"] = str(e)

    metrics = {
        "tags_count": len(tags_found),
        "tags": tags_found,
    }
    return findings, metrics


def run_all_heuristics(
    file_path: str,
    y: np.ndarray,
    sr: int = 16000,
    short_clip_padded: bool = False,
) -> Tuple[List[Finding], Dict[str, Any]]:
    """
    Runs all 5 heuristic edit/splice checks and returns aggregate findings and raw metrics.
    Heuristic checks only produce 'low' or 'medium' severity findings and never dictate the verdict.
    """
    all_findings: List[Finding] = []
    raw_heuristics: Dict[str, Any] = {}

    # 1. Noise floor jump
    f_noise, m_noise = detect_noise_floor_jump(y, sr)
    all_findings.extend(f_noise)
    raw_heuristics["noise_floor_jump"] = m_noise

    # 2. Spectral discontinuity
    f_spec, m_spec = detect_spectral_discontinuity(y, sr)
    all_findings.extend(f_spec)
    raw_heuristics["spectral_discontinuity"] = m_spec

    # 3. Repeated segment (skipped if clip was short_clip_padded)
    f_rep, m_rep = detect_repeated_segment(y, sr, short_clip_padded=short_clip_padded)
    all_findings.extend(f_rep)
    raw_heuristics["repeated_segment"] = m_rep

    # 4. Bandwidth inconsistency
    f_bw, m_bw = detect_bandwidth_inconsistency(y, sr)
    all_findings.extend(f_bw)
    raw_heuristics["bandwidth_inconsistency"] = m_bw

    # 5. Metadata flags
    f_meta, m_meta = inspect_metadata_flags(file_path)
    all_findings.extend(f_meta)
    raw_heuristics["metadata_flags"] = m_meta

    # Enforce strict guarantee: Heuristics may only produce findings of severity 'low' or 'medium'
    for f in all_findings:
        if f.severity == "high":
            f.severity = "medium"

    return all_findings, raw_heuristics
