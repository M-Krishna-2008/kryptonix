from __future__ import annotations
import numpy as np
import pytest
from pathlib import Path

from audio_forensics.config import SAMPLE_RATE, WINDOW_SAMPLES, HOP_SAMPLES
from audio_forensics.audio_preprocess import (
    resample_to_16k,
    preprocess_and_window,
)
from audio_forensics.tests.make_samples import write_wav


def test_resample_to_16k():
    orig_sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(orig_sr * duration), endpoint=False)
    # 440 Hz sine wave
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    resampled = resample_to_16k(sine, orig_sr, SAMPLE_RATE)
    assert len(resampled) == int(duration * SAMPLE_RATE)
    assert resampled.dtype == np.float32


def test_window_short_clip(tmp_path: Path):
    # Clip shorter than 64,600 samples (2.0s = 32,000 samples)
    t = np.linspace(0, 2.0, 32000, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    wav_path = tmp_path / "short.wav"
    write_wav(wav_path, audio, SAMPLE_RATE)

    res = preprocess_and_window(wav_path)
    assert len(res["errors"]) == 0
    assert res["flags"]["short_clip_padded"] is True
    assert len(res["windows"]) == 1
    assert len(res["windows"][0]) == WINDOW_SAMPLES


def test_window_long_clip(tmp_path: Path):
    # Clip of 10.0 seconds (160,000 samples)
    t = np.linspace(0, 10.0, 160000, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    wav_path = tmp_path / "long.wav"
    write_wav(wav_path, audio, SAMPLE_RATE)

    res = preprocess_and_window(wav_path)
    assert len(res["errors"]) == 0
    assert res["flags"]["short_clip_padded"] is False
    assert len(res["windows"]) >= 3
    for w in res["windows"]:
        assert len(w) == WINDOW_SAMPLES


def test_empty_and_silent_clip(tmp_path: Path):
    # 1. 0-byte file
    empty_file = tmp_path / "empty.wav"
    empty_file.write_bytes(b"")
    res_empty = preprocess_and_window(empty_file)
    assert len(res_empty["errors"]) > 0

    # 2. Silent file
    silent_file = tmp_path / "silent.wav"
    silent_audio = np.zeros(16000, dtype=np.float32)
    write_wav(silent_file, silent_audio, SAMPLE_RATE)
    res_silent = preprocess_and_window(silent_file)
    assert res_silent["flags"]["is_silent"] is True
    assert any("silent" in err.lower() for err in res_silent["errors"])
