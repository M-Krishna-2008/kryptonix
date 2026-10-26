from __future__ import annotations
import math
from pathlib import Path
import wave
import struct
import numpy as np

SAMPLE_RATE = 16000
TESTS_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = TESTS_DIR / "samples"
REAL_DIR = SAMPLES_DIR / "real"
SYNTHETIC_DIR = SAMPLES_DIR / "synthetic"
TAMPERED_DIR = SAMPLES_DIR / "tampered"

for d in [REAL_DIR, SYNTHETIC_DIR, TAMPERED_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def write_wav(path: Path, data: np.ndarray, sr: int = SAMPLE_RATE):
    """Writes 1D float32 numpy array to 16-bit PCM WAV."""
    data_clamped = np.clip(data, -1.0, 1.0)
    int16_data = (data_clamped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data.tobytes())


def generate_tts_sample_pyttsx3(output_path: Path, text: str):
    """Generates synthetic speech using pyttsx3 (Windows SAPI5 voice engine)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        # Save to wav
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        print(f"Generated TTS sample via pyttsx3: {output_path}")
        return True
    except Exception as e:
        print(f"pyttsx3 generation failed ({e}), falling back to robotic synthesizer...")
        return False


def generate_synthetic_formant_speech(output_path: Path, duration_sec: float = 5.0):
    """
    Fallback robotic speech synthesizer generating unnatural, rigidly harmonic
    synthetic vocal tract resonances with zero natural micro-jitter.
    """
    sr = SAMPLE_RATE
    total_samples = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # Completely rigid synthetic pitch (F0 = 130 Hz without natural vocal jitter)
    f0 = 130.0
    glottal = np.zeros(total_samples, dtype=np.float32)
    for harmonic in range(1, 25):
        amp = 1.0 / (harmonic ** 1.3)
        glottal += amp * np.sin(2.0 * np.pi * f0 * harmonic * t)

    # Formant filters (F1=500Hz, F2=1500Hz, F3=2500Hz)
    formant1 = np.exp(-((t % 0.3) * 10)) * np.sin(2 * np.pi * 500 * t)
    formant2 = np.exp(-((t % 0.3) * 15)) * np.sin(2 * np.pi * 1500 * t)
    audio = 0.5 * glottal + 0.3 * formant1 + 0.2 * formant2

    # Unnatural square-wave amplitude gating (typical of crude synthetic engines)
    gate = (np.sin(2 * np.pi * 3.5 * t) > 0.0).astype(float)
    audio = audio * gate
    # Normalize
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.85
    write_wav(output_path, audio.astype(np.float32))
    print(f"Generated synthetic voice proxy: {output_path}")


def generate_natural_voice_proxy(output_path: Path, duration_sec: float = 6.0):
    """
    Generates an acoustic voice proxy with natural pitch variations (vibrato/jitter),
    subtle room reverberation, and warm human acoustic spectral decay.
    """
    sr = SAMPLE_RATE
    total_samples = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # Natural micro-jitter and pitch contour (120 Hz to 145 Hz modulation)
    f0_contour = 130.0 + 12.0 * np.sin(2 * np.pi * 0.7 * t) + 2.5 * np.sin(2 * np.pi * 4.5 * t)
    phase = 2.0 * np.pi * np.cumsum(f0_contour) / float(sr)

    # Harmonic series with soft exponential rolloff
    signal = np.zeros(total_samples, dtype=np.float32)
    for h in range(1, 20):
        amp = np.exp(-h * 0.25)
        signal += amp * np.sin(h * phase)

    # Natural smooth syllabic envelope
    envelope = np.abs(np.sin(2 * np.pi * 1.8 * t)) ** 1.5
    # Add subtle pink background room noise
    noise = np.random.normal(0, 0.015, total_samples).astype(np.float32)
    audio = (signal * envelope * 0.7) + noise

    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.8
    write_wav(output_path, audio.astype(np.float32))
    print(f"Generated acoustic voice proxy: {output_path}")


def generate_spliced_sample(output_path: Path):
    """
    Generates a tampered audio sample featuring an abrupt 15 dB noise floor jump
    and spliced synthetic insert between 2.0s and 5.0s.
    """
    sr = SAMPLE_RATE
    t = np.linspace(0, 7.0, 7 * sr, endpoint=False)
    # Part 1: Quiet room background (0s to 2.5s)
    p1 = np.random.normal(0, 0.005, int(2.5 * sr))
    # Part 2: Loud foreign background noise + synthetic tone (2.5s to 5.0s, +16 dB jump)
    p2 = np.random.normal(0, 0.035, int(2.5 * sr)) + 0.3 * np.sin(2 * np.pi * 440 * t[: int(2.5 * sr)])
    # Part 3: Back to quiet background (5.0s to 7.0s)
    p3 = np.random.normal(0, 0.005, int(2.0 * sr))

    audio = np.concatenate([p1, p2, p3])
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.8
    write_wav(output_path, audio.astype(np.float32))
    print(f"Generated spliced tampering sample: {output_path}")


def create_all_samples():
    print("Generating test evidence audio samples...")

    # 1. Synthetic speech
    synth1_path = SYNTHETIC_DIR / "synthetic_speech_sapi.wav"
    text1 = "This is a computer generated synthetic voice designed to test the audio authenticity detector."
    if not generate_tts_sample_pyttsx3(synth1_path, text1):
        generate_synthetic_formant_speech(synth1_path, duration_sec=5.0)

    synth2_path = SYNTHETIC_DIR / "synthetic_robotic_sample.wav"
    generate_synthetic_formant_speech(synth2_path, duration_sec=5.0)

    # 2. Authentic speech proxy
    real_path = REAL_DIR / "sample_voice_real.wav"
    generate_natural_voice_proxy(real_path, duration_sec=6.0)

    # 3. Spliced tampering sample
    tampered_path = TAMPERED_DIR / "spliced_tampered.wav"
    generate_spliced_sample(tampered_path)

    print("\nSample generation complete!")


if __name__ == "__main__":
    create_all_samples()
