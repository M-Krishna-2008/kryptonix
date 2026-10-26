from __future__ import annotations
import numpy as np
import pytest

from audio_forensics.heuristics import (
    detect_noise_floor_jump,
    detect_spectral_discontinuity,
    detect_repeated_segment,
    detect_bandwidth_inconsistency,
)


def test_noise_floor_jump_detection():
    sr = 16000
    # Create two halves: first half quiet noise (std=0.005), second half loud noise (std=0.040, ~18dB jump)
    n1 = np.random.normal(0, 0.005, 3 * sr).astype(np.float32)
    n2 = np.random.normal(0, 0.040, 3 * sr).astype(np.float32)
    audio = np.concatenate([n1, n2])

    findings, metrics = detect_noise_floor_jump(audio, sr=sr, jump_threshold_db=12.0)
    assert metrics["checked"] is True
    assert metrics["max_noise_jump_db"] >= 12.0
    assert len(findings) > 0
    assert findings[0].check == "noise_floor_jump"
    assert findings[0].location is not None


def test_spectral_discontinuity_detection():
    sr = 16000
    # Clean continuous sine wave interrupted by a sudden high-energy white-noise click at 2.0s
    t = np.linspace(0, 4.0, 4 * sr, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    click_idx = int(2.0 * sr)
    audio[click_idx : click_idx + 100] += np.random.normal(0, 0.9, 100).astype(np.float32)

    findings, metrics = detect_spectral_discontinuity(audio, sr=sr)
    assert metrics["checked"] is True
    assert len(findings) > 0
    assert findings[0].check == "spectral_discontinuity"


def test_repeated_segment_detection():
    sr = 16000
    t = np.linspace(0, 1.0, 1 * sr, endpoint=False)
    # Distinct modulated chirp pattern
    chirp = (0.5 * np.sin(2 * np.pi * (200 + 300 * t) * t)).astype(np.float32)

    # Place the same 1-second segment at 0.0s and at 3.0s
    audio = np.random.normal(0, 0.01, 5 * sr).astype(np.float32)
    audio[0 : 1 * sr] += chirp
    audio[3 * sr : 4 * sr] += chirp

    findings, metrics = detect_repeated_segment(audio, sr=sr, segment_sec=1.0)
    assert metrics["checked"] is True
    assert metrics["max_segment_correlation"] >= 0.90
    assert len(findings) > 0
    assert findings[0].check == "repeated_segment"


def test_bandwidth_inconsistency():
    sr = 16000
    t = np.linspace(0, 3.0, 3 * sr, endpoint=False)
    # Segment 1: Low-passed audio (only frequencies below 2000 Hz)
    seg1 = (0.5 * np.sin(2 * np.pi * 600 * t)).astype(np.float32)
    # Segment 2: Wideband audio with strong 6500 Hz high frequency
    seg2 = (0.3 * np.sin(2 * np.pi * 600 * t) + 0.3 * np.sin(2 * np.pi * 6500 * t)).astype(np.float32)
    audio = np.concatenate([seg1, seg2])

    findings, metrics = detect_bandwidth_inconsistency(audio, sr=sr, win_sec=2.0)
    assert metrics["checked"] is True
    assert metrics["delta_hz"] >= 2500.0
    assert len(findings) > 0
    assert findings[0].check == "bandwidth_inconsistency"
