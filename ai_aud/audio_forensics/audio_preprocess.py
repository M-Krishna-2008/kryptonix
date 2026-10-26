from __future__ import annotations
import math
from pathlib import Path
from typing import Tuple, List, Dict, Any
import numpy as np

from .config import (
    SAMPLE_RATE,
    WINDOW_SAMPLES,
    HOP_SAMPLES,
    MAX_DURATION_SEC,
)


def decode_audio(file_path: str | Path) -> Tuple[np.ndarray, int]:
    """
    Decodes audio from file_path into a mono float32 numpy array and returns (waveform, original_sr).
    Tries soundfile first, falls back to librosa, then PyAV.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {file_path}")

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise ValueError("Audio file is completely empty (0 bytes).")

    # Attempt 1: soundfile
    try:
        import soundfile as sf
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if data.size == 0:
            raise ValueError("Decoded audio contains 0 samples.")
        if data.ndim > 1:
            # Average channels to mono
            data = np.mean(data, axis=1)
        return data.astype(np.float32), sr
    except Exception as sf_err:
        last_err = sf_err

    # Attempt 2: PyAV (av)
    try:
        import av
        container = av.open(str(path))
        audio_streams = [s for s in container.streams if s.type == "audio"]
        if not audio_streams:
            raise ValueError("No audio streams found in container.")
        
        frames = []
        sr = audio_streams[0].codec_context.sample_rate or 44100
        for frame in container.decode(audio_streams[0]):
            arr = frame.to_ndarray()
            # shape can be (channels, samples) or (samples, channels)
            if arr.ndim > 1:
                arr = np.mean(arr, axis=0 if arr.shape[0] < arr.shape[1] else 1)
            frames.append(arr)
        container.close()

        if not frames:
            raise ValueError("PyAV decoded 0 audio frames.")
        data = np.concatenate(frames).astype(np.float32)
        # Normalize int16/int32 to float32 range if needed
        if np.issubdtype(data.dtype, np.integer):
            info = np.iinfo(data.dtype)
            data = data / max(abs(info.min), abs(info.max))
        return data.astype(np.float32), sr
    except Exception as av_err:
        last_err = av_err

    # Attempt 3: librosa
    try:
        import librosa
        data, sr = librosa.load(str(path), sr=None, mono=True)
        if data.size == 0:
            raise ValueError("Librosa loaded 0 samples.")
        return data.astype(np.float32), sr
    except Exception as lr_err:
        raise ValueError(f"Failed to decode audio file ({path.suffix}): {last_err}; Librosa fallback: {lr_err}")


def resample_to_16k(audio: np.ndarray, orig_sr: int, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    TRULY resamples mono audio to 16 kHz using scipy.signal.resample_poly
    or librosa.resample.
    """
    if orig_sr == target_sr:
        return audio.astype(np.float32)

    try:
        from scipy.signal import resample_poly
        gcd = math.gcd(orig_sr, target_sr)
        up = target_sr // gcd
        down = orig_sr // gcd
        resampled = resample_poly(audio, up, down).astype(np.float32)
        return resampled
    except Exception:
        pass

    try:
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr).astype(np.float32)
    except Exception:
        # Fallback linear interpolation
        duration = len(audio) / orig_sr
        target_len = int(duration * target_sr)
        x_old = np.linspace(0, 1, len(audio))
        x_new = np.linspace(0, 1, target_len)
        return np.interp(x_new, x_old, audio).astype(np.float32)


def detect_container_codec(file_path: str | Path) -> Dict[str, Any]:
    """
    Detects container format, audio codec, bitrate, lossy classification,
    and returns a profile ('lossless', 'lossy_high_bitrate', 'lossy_low_bitrate').
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    # Defaults based on suffix
    is_lossless_ext = suffix in {".wav", ".flac", ".aif", ".aiff", ".alac"}
    codec_name = suffix.lstrip(".")
    fmt_name = suffix.lstrip(".")
    bitrate_kbps: int | None = None

    try:
        import av
        with av.open(str(path)) as container:
            if container.format and container.format.name:
                fmt_name = container.format.name.lower()
            audio_streams = [s for s in container.streams if s.type == "audio"]
            if audio_streams:
                s = audio_streams[0]
                if s.codec_context and s.codec_context.name:
                    codec_name = s.codec_context.name.lower()
                br = s.bit_rate or container.bit_rate
                if br and br > 0:
                    bitrate_kbps = int(round(br / 1000.0))
    except Exception:
        pass

    # Classify codec
    lossless_patterns = ("flac", "pcm", "alac", "wav")
    is_lossless = is_lossless_ext or any(p in codec_name for p in lossless_patterns)

    if is_lossless:
        is_lossy = False
        codec_class = "lossless"
    else:
        is_lossy = True
        if bitrate_kbps is None:
            try:
                import soundfile as sf
                f = sf.SoundFile(str(path))
                dur = f.frames / float(f.samplerate)
                if dur > 0:
                    bitrate_kbps = int(round((path.stat().st_size * 8) / (dur * 1000.0)))
            except Exception:
                bitrate_kbps = 128

        if bitrate_kbps is not None and bitrate_kbps < 128:
            codec_class = "lossy_low_bitrate"
        else:
            codec_class = "lossy_high_bitrate"

    return {
        "format": fmt_name,
        "codec": codec_name,
        "bitrate_kbps": bitrate_kbps,
        "is_lossy": is_lossy,
        "codec_class": codec_class,
    }


def compute_vad_speech_frames(y: np.ndarray, sr: int = SAMPLE_RATE, frame_ms: int = 30) -> np.ndarray:
    """
    Computes frame-level voice activity detection (VAD).
    Returns boolean array of speech indicators for each frame_ms window.
    Uses webrtcvad if installed/functional, with energy-based RMS gating fallback.
    """
    frame_samples = int(sr * (frame_ms / 1000.0))
    if frame_samples <= 0 or len(y) < frame_samples:
        return np.zeros(0, dtype=bool)

    n_frames = len(y) // frame_samples
    speech_flags = np.zeros(n_frames, dtype=bool)

    # Attempt 1: webrtcvad
    try:
        import webrtcvad
        vad = webrtcvad.Vad(2)  # Mode 2: balanced aggressiveness
        for i in range(n_frames):
            chunk = y[i * frame_samples : (i + 1) * frame_samples]
            pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            speech_flags[i] = vad.is_speech(pcm16, sr)
        return speech_flags
    except Exception:
        pass

    # Fallback: Energy / RMS gating
    rms_vals = [
        float(np.sqrt(np.mean(y[i * frame_samples : (i + 1) * frame_samples] ** 2) + 1e-12))
        for i in range(n_frames)
    ]
    if not rms_vals:
        return np.zeros(0, dtype=bool)

    p30 = float(np.percentile(rms_vals, 30))
    p70 = float(np.percentile(rms_vals, 70))
    adaptive_thresh = max(1e-3, p30 + 0.15 * (p70 - p30))

    for i in range(n_frames):
        speech_flags[i] = rms_vals[i] >= adaptive_thresh

    return speech_flags


def preprocess_and_window(
    file_path: str | Path,
    max_duration_sec: float = MAX_DURATION_SEC,
    vad_ratio_threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Decodes, converts to mono, resamples to 16 kHz, runs VAD, detects container codec,
    and generates 64,600-sample windows with speech metadata.
    """
    errors: List[str] = []
    path = Path(file_path)

    codec_info = detect_container_codec(path)

    try:
        raw_audio, orig_sr = decode_audio(path)
    except Exception as e:
        return {
            "waveform": np.zeros(0, dtype=np.float32),
            "orig_sr": 0,
            "sample_rate": SAMPLE_RATE,
            "duration_sec": 0.0,
            "windows": [],
            "window_meta": [],
            "flags": {
                "short_clip_padded": False,
                "truncated": False,
                "is_silent": True,
                "rms": 0.0,
                "codec_info": codec_info,
            },
            "errors": [f"Audio decoding failure: {str(e)}"],
        }

    # Resample to 16 kHz
    y = resample_to_16k(raw_audio, orig_sr, SAMPLE_RATE)

    # Peak normalization / clipping prevention
    peak = float(np.max(np.abs(y))) if len(y) > 0 else 0.0
    if peak > 1.0:
        y = y / peak

    total_samples = len(y)
    duration_sec = total_samples / float(SAMPLE_RATE)
    truncated = False

    # Check for duration cap
    max_samples = int(max_duration_sec * SAMPLE_RATE)
    if total_samples > max_samples:
        y = y[:max_samples]
        truncated = True
        total_samples = max_samples
        duration_sec = max_duration_sec

    # Silence check
    rms = float(np.sqrt(np.mean(y**2))) if total_samples > 0 else 0.0
    is_silent = (rms < 1e-4) or (peak < 1e-3)
    if is_silent:
        errors.append("Audio recording is silent or contains negligible acoustic energy (RMS < 1e-4).")

    # Compute VAD frames (30ms per frame = 480 samples at 16kHz)
    vad_frame_samples = int(SAMPLE_RATE * 0.030)
    speech_flags = compute_vad_speech_frames(y, SAMPLE_RATE, 30)

    windows: List[np.ndarray] = []
    window_meta: List[Dict[str, Any]] = []
    short_clip_padded = False

    def evaluate_window_speech(s_sample: int, e_sample: int) -> Tuple[float, bool]:
        if len(speech_flags) == 0:
            return 1.0 if not is_silent else 0.0, not is_silent
        s_idx = max(0, s_sample // vad_frame_samples)
        e_idx = min(len(speech_flags), int(math.ceil(e_sample / vad_frame_samples)))
        if e_idx <= s_idx:
            ratio = 1.0 if speech_flags[min(s_idx, len(speech_flags)-1)] else 0.0
        else:
            ratio = float(np.mean(speech_flags[s_idx:e_idx]))
        return ratio, bool(ratio >= vad_ratio_threshold)

    if total_samples == 0:
        errors.append("Audio recording contains 0 usable samples.")
    elif total_samples < WINDOW_SAMPLES:
        # Tile / repeat short clip to reach exactly 64,600 samples
        repeats = int(math.ceil(WINDOW_SAMPLES / total_samples))
        tiled = np.tile(y, repeats)[:WINDOW_SAMPLES].astype(np.float32)
        windows.append(tiled)
        s_ratio, has_sp = evaluate_window_speech(0, total_samples)
        window_meta.append({
            "index": 0,
            "start_sample": 0,
            "end_sample": total_samples,
            "start_sec": 0.0,
            "end_sec": duration_sec,
            "is_padded": True,
            "speech_ratio": round(s_ratio, 3),
            "has_speech": has_sp,
        })
        short_clip_padded = True
    else:
        # Sliding windows with 50% overlap
        num_hops = max(1, int(math.floor((total_samples - WINDOW_SAMPLES) / HOP_SAMPLES)) + 1)
        for i in range(num_hops):
            start = i * HOP_SAMPLES
            end = start + WINDOW_SAMPLES
            if end > total_samples:
                break
            w = y[start:end].astype(np.float32)
            windows.append(w)
            s_ratio, has_sp = evaluate_window_speech(start, end)
            window_meta.append({
                "index": i,
                "start_sample": start,
                "end_sample": end,
                "start_sec": round(start / float(SAMPLE_RATE), 3),
                "end_sec": round(end / float(SAMPLE_RATE), 3),
                "is_padded": False,
                "speech_ratio": round(s_ratio, 3),
                "has_speech": has_sp,
            })

        # If significant audio remains at tail (> 1 second), include final tail window
        last_end = window_meta[-1]["end_sample"] if window_meta else 0
        if total_samples - last_end >= SAMPLE_RATE:
            start = total_samples - WINDOW_SAMPLES
            end = total_samples
            w = y[start:end].astype(np.float32)
            windows.append(w)
            s_ratio, has_sp = evaluate_window_speech(start, end)
            window_meta.append({
                "index": len(window_meta),
                "start_sample": start,
                "end_sample": end,
                "start_sec": round(start / float(SAMPLE_RATE), 3),
                "end_sec": round(end / float(SAMPLE_RATE), 3),
                "is_padded": False,
                "speech_ratio": round(s_ratio, 3),
                "has_speech": has_sp,
            })

    speech_windows_count = sum(1 for m in window_meta if m.get("has_speech", True))
    non_speech_windows_count = len(window_meta) - speech_windows_count

    return {
        "waveform": y,
        "orig_sr": orig_sr,
        "sample_rate": SAMPLE_RATE,
        "duration_sec": round(duration_sec, 3),
        "windows": windows,
        "window_meta": window_meta,
        "codec_info": codec_info,
        "flags": {
            "short_clip_padded": short_clip_padded,
            "truncated": truncated,
            "is_silent": is_silent,
            "rms": round(rms, 6),
            "peak": round(peak, 4),
            "codec_info": codec_info,
            "speech_windows_count": speech_windows_count,
            "non_speech_windows_count": non_speech_windows_count,
        },
        "errors": errors,
    }

