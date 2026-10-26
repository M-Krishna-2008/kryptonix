from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

# Ensure matplotlib runs in headless / non-GUI mode
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_visual_artifacts(
    y: np.ndarray,
    sr: int,
    window_meta: List[Dict[str, Any]],
    logits: np.ndarray,
    low_thresh: float,
    high_thresh: float,
    change_points: List[float],
    artifacts_dir: Path,
    sha256_prefix: str = "evidence",
) -> Dict[str, str]:
    """
    Generates 3 visual evidence artifacts:
      1. waveform_analysis.png: Waveform with shaded suspicious segments
      2. spectrogram_analysis.png: Log-spectrogram with change points marked
      3. logit_timeline.png: Per-window logit timeline with threshold boundaries
    Returns mapping of artifact keys to relative filenames.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    duration_sec = len(y) / float(sr) if sr > 0 else 0.0
    times = np.linspace(0, duration_sec, len(y)) if len(y) > 0 else np.zeros(0)

    # -------------------------------------------------------------
    # 1. Waveform Plot with Suspicious Regions
    # -------------------------------------------------------------
    wf_name = f"{sha256_prefix}_waveform.png"
    wf_path = artifacts_dir / wf_name

    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=100)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    # Downsample waveform for plotting speed if long
    downsample = max(1, len(y) // 20000)
    y_sub = y[::downsample]
    t_sub = times[::downsample]

    ax.plot(t_sub, y_sub, color="#38bdf8", linewidth=0.8, alpha=0.9, label="Waveform")

    # Shade windows: Red for suspicious speech, Grey for no-speech
    shaded_susp_label = False
    shaded_nospeech_label = False
    if len(logits) == len(window_meta):
        for idx, logit in enumerate(logits):
            meta = window_meta[idx]
            s_sec = meta.get("start_sec", 0.0)
            e_sec = meta.get("end_sec", 0.0)
            has_sp = meta.get("has_speech", True)

            if not has_sp:
                ax.axvspan(
                    s_sec,
                    e_sec,
                    color="#64748b",
                    alpha=0.20,
                    label="No Speech (Excluded)" if not shaded_nospeech_label else None,
                )
                shaded_nospeech_label = True
            elif logit is not None and not (np.isnan(logit) or np.isinf(logit)) and logit < low_thresh:
                ax.axvspan(
                    s_sec,
                    e_sec,
                    color="#ef4444",
                    alpha=0.25,
                    label="Suspicious Window (AASIST)" if not shaded_susp_label else None,
                )
                shaded_susp_label = True

    ax.set_xlim(0, max(duration_sec, 0.1))
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("Time (seconds)", color="#94a3b8", fontsize=10)
    ax.set_ylabel("Amplitude", color="#94a3b8", fontsize=10)
    ax.set_title("Audio Waveform & Tampered / Synthetic Detection Regions", color="#f8fafc", fontsize=12, fontweight="bold")
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    if shaded_susp_label or shaded_nospeech_label:
        ax.legend(loc="upper right", facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc")

    fig.tight_layout()
    fig.savefig(wf_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    results["waveform"] = wf_name

    # -------------------------------------------------------------
    # 2. Spectrogram Plot with Marked Discontinuities
    # -------------------------------------------------------------
    spec_name = f"{sha256_prefix}_spectrogram.png"
    spec_path = artifacts_dir / spec_name

    fig, ax = plt.subplots(figsize=(10, 4.0), dpi=100)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    if len(y) > 512:
        # Compute STFT
        try:
            from scipy.signal import stft
            f, t, Zxx = stft(y, fs=sr, nperseg=512, noverlap=384)
            spec_db = 20 * np.log10(np.abs(Zxx) + 1e-6)
            spec_db = np.clip(spec_db, -80, 0)
            img = ax.pcolormesh(t, f, spec_db, shading="gouraud", cmap="magma")
            cbar = fig.colorbar(img, ax=ax, pad=0.02)
            cbar.set_label("Magnitude (dB)", color="#94a3b8")
            cbar.ax.tick_params(colors="#94a3b8")
        except Exception:
            ax.specgram(y, Fs=sr, NFFT=512, noverlap=384, cmap="magma")
    else:
        ax.text(0.5, 0.5, "Audio sample too short for spectrogram analysis", color="#94a3b8", ha="center")

    # Mark splice / discontinuity change points
    for idx, cp in enumerate(change_points):
        ax.axvline(
            cp,
            color="#fbbf24",
            linestyle="--",
            linewidth=1.5,
            label="Splice / Change Point" if idx == 0 else None,
        )

    ax.set_xlim(0, max(duration_sec, 0.1))
    ax.set_ylim(0, sr // 2)
    ax.set_xlabel("Time (seconds)", color="#94a3b8", fontsize=10)
    ax.set_ylabel("Frequency (Hz)", color="#94a3b8", fontsize=10)
    ax.set_title("Spectral Energy Distribution & Discontinuity Markers", color="#f8fafc", fontsize=12, fontweight="bold")
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    if change_points:
        ax.legend(loc="upper right", facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc")

    fig.tight_layout()
    fig.savefig(spec_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    results["spectrogram"] = spec_name

    # -------------------------------------------------------------
    # 3. Logit Timeline Plot with Threshold Bands & VAD Grey-out
    # -------------------------------------------------------------
    tl_name = f"{sha256_prefix}_timeline.png"
    tl_path = artifacts_dir / tl_name

    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=100)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    valid_logits = [float(l) for l in logits if l is not None and not (np.isnan(l) or np.isinf(l))] if len(logits) > 0 else []
    if len(valid_logits) > 0 and len(window_meta) == len(logits):
        w_centers = [(m["start_sec"] + m["end_sec"]) / 2.0 for m in window_meta]

        sp_indices = [i for i, m in enumerate(window_meta) if m.get("has_speech", True) and logits[i] is not None and not (np.isnan(logits[i]) or np.isinf(logits[i]))]
        non_sp_indices = [i for i, m in enumerate(window_meta) if not m.get("has_speech", True) or logits[i] is None or np.isnan(logits[i]) or np.isinf(logits[i])]

        # Plot speech windows line and points
        if sp_indices:
            sp_centers = [w_centers[i] for i in sp_indices]
            sp_logits = [logits[i] for i in sp_indices]
            ax.plot(sp_centers, sp_logits, color="#38bdf8", marker="o", markersize=4, linewidth=1.5, label="Bona-Fide Logit (Speech)")

        # Plot greyed out non-speech windows
        if non_sp_indices:
            non_sp_centers = [w_centers[i] for i in non_sp_indices]
            non_sp_logits = [logits[i] if (logits[i] is not None and not np.isnan(logits[i])) else 0.0 for i in non_sp_indices]
            ax.scatter(non_sp_centers, non_sp_logits, color="#64748b", marker="x", s=35, zorder=4, label="No speech / invalid (excluded)")
            for i in non_sp_indices:
                meta = window_meta[i]
                ax.axvspan(meta["start_sec"], meta["end_sec"], color="#334155", alpha=0.35)

        # Threshold lines
        ax.axhline(high_thresh, color="#22c55e", linestyle="--", linewidth=1.2, label=f"Authentic Thresh ({high_thresh:.1f})")
        ax.axhline(low_thresh, color="#ef4444", linestyle="--", linewidth=1.2, label=f"Synthetic Thresh ({low_thresh:.1f})")

        # Uncertain band shading
        ax.axhspan(low_thresh, high_thresh, color="#f59e0b", alpha=0.15, label="Uncertain Band")

        y_min = min(float(np.nanmin(valid_logits)) - 1.0, low_thresh - 1.5)
        y_max = max(float(np.nanmax(valid_logits)) + 1.0, high_thresh + 1.5)
        ax.set_ylim(y_min, y_max)
    else:
        ax.text(0.5, 0.5, "No model logits available", color="#94a3b8", ha="center")
        ax.set_ylim(-3, 3)

    ax.set_xlim(0, max(duration_sec, 0.1))
    ax.set_xlabel("Time (seconds)", color="#94a3b8", fontsize=10)
    ax.set_ylabel("Score (Logit: higher = genuine)", color="#94a3b8", fontsize=10)
    ax.set_title("Per-Window W2V2-AASIST Detection Scores Timeline (Speech vs Non-Speech)", color="#f8fafc", fontsize=12, fontweight="bold")
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper right", facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc", fontsize=8)

    fig.tight_layout()
    fig.savefig(tl_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    results["timeline"] = tl_name

    return results

