from __future__ import annotations
import io
import numpy as np
import pytest
from fastapi.testclient import TestClient

from main_standalone import app
from audio_forensics.schemas import AnalysisResult
from audio_forensics.tests.make_samples import write_wav

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/audio_forensics/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["module"] == "audio_forensics"


def test_analyze_endpoint_with_wav(tmp_path):
    wav_path = tmp_path / "test_api.wav"
    # 3-second tone
    t = np.linspace(0, 3.0, 3 * 16000, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    write_wav(wav_path, audio, 16000)

    with open(wav_path, "rb") as f:
        resp = client.post("/api/audio_forensics/analyze", files={"file": ("test_api.wav", f, "audio/wav")})

    assert resp.status_code == 200
    data = resp.json()

    # Validate against standard Pydantic schema
    validated = AnalysisResult(**data)
    assert validated.module == "audio_forensics"
    assert validated.version == "1.0"
    assert validated.verdict in ["authentic", "suspicious", "likely_tampered", "inconclusive"]
    assert 0.0 <= validated.overall_confidence <= 1.0
    assert validated.evidence_file.name == "test_api.wav"
    assert len(validated.evidence_file.sha256) == 64
    assert len(validated.findings) > 0


def test_progress_endpoint():
    resp = client.get("/api/audio_forensics/progress/test-job-id")
    assert resp.status_code == 200
    data = resp.json()
    assert "stage" in data
    assert "percent" in data
