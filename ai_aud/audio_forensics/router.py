from __future__ import annotations
import asyncio
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from .config import (
    MODULE_DIR,
    UPLOAD_DIR,
    ARTIFACT_DIR,
    CACHE_DIR,
    MAX_UPLOAD_BYTES,
    XLSR_MODEL_PATH,
    AASIST_MODEL_PATH,
)
from .schemas import HealthResponse, ProgressResponse
from .analyzer import analyze, compute_sha256, compute_file_hash

logger = logging.getLogger("audio_forensics.router")

router = APIRouter(prefix="/api/audio_forensics", tags=["audio_forensics"])

# In-memory progress tracking for background tasks
JOB_PROGRESS: Dict[str, Dict[str, Any]] = {}


def get_cache_key(file_sha256: str) -> str:
    m_xlsr = compute_file_hash(XLSR_MODEL_PATH) or "no_xlsr"
    m_aasist = compute_file_hash(AASIST_MODEL_PATH) or "no_aasist"
    return f"{file_sha256}_{m_xlsr}_{m_aasist}.json"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint as specified in integration contract."""
    return HealthResponse(status="ok", module="audio_forensics")


@router.get("/artifacts/{filename}")
async def get_artifact(filename: str):
    """Serves generated visual evidence artifacts (waveform, spectrogram, timeline)."""
    # Prevent path traversal
    safe_name = Path(filename).name
    file_path = ARTIFACT_DIR / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(path=str(file_path))


@router.get("/progress/{job_id}", response_model=ProgressResponse)
async def get_progress(job_id: str):
    """Reports background analysis progress for large evidence recordings."""
    if job_id not in JOB_PROGRESS:
        return ProgressResponse(job_id=job_id, stage="completed", percent=100)
    prog = JOB_PROGRESS[job_id]
    return ProgressResponse(
        job_id=job_id,
        stage=prog.get("stage", "processing"),
        percent=int(prog.get("percent", 0)),
    )


@router.post("/analyze")
async def analyze_audio(
    file: UploadFile = File(...),
):
    """
    Standard analysis endpoint: accepts multipart upload, computes authenticity verification,
    checks cache, and returns standard result JSON.
    """
    job_id = str(uuid.uuid4())
    JOB_PROGRESS[job_id] = {"stage": "uploading", "percent": 10}

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_filename = f"{job_id}_{Path(file.filename or 'audio.wav').name}"
    dest_path = UPLOAD_DIR / temp_filename

    total_bytes = 0
    try:
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded file exceeds maximum allowed limit of {MAX_UPLOAD_BYTES // (1024*1024)} MB."
                    )
                buffer.write(chunk)
    except HTTPException:
        if dest_path.exists():
            dest_path.unlink()
        raise
    except Exception as e:
        logger.error(f"Failed to stream uploaded file: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    JOB_PROGRESS[job_id] = {"stage": "checking_cache", "percent": 25}

    # Compute SHA-256 for caching
    file_sha256 = compute_sha256(dest_path)
    cache_file = CACHE_DIR / get_cache_key(file_sha256)

    # Check cache
    if cache_file.is_file():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            # Only use cache if it was a successful analysis without model or fatal errors
            cached_errors = cached_data.get("errors", [])
            has_checkpoint_err = any("checkpoint" in str(e).lower() or "not installed" in str(e).lower() for e in cached_errors)
            if not has_checkpoint_err and cached_data.get("raw_metrics"):
                if file.filename:
                    cached_data["evidence_file"]["name"] = file.filename
                JOB_PROGRESS[job_id] = {"stage": "completed", "percent": 100}
                # Clean up uploaded audio unless configured to keep
                try:
                    dest_path.unlink()
                except Exception:
                    pass
                return JSONResponse(content=cached_data)
        except Exception:
            pass

    JOB_PROGRESS[job_id] = {"stage": "analyzing_acoustic_features", "percent": 50}

    # Execute core analysis
    try:
        # Run synchronous analysis in thread pool so it does not block the async event loop
        loop = asyncio.get_event_loop()
        JOB_PROGRESS[job_id] = {"stage": "scoring_model_and_heuristics", "percent": 75}
        options = {"original_filename": file.filename}
        result = await loop.run_in_executor(None, analyze, str(dest_path), options)

        JOB_PROGRESS[job_id] = {"stage": "generating_visual_evidence", "percent": 90}

        # Cache result only if analysis had no model checkpoint or server errors
        res_errors = result.get("errors", [])
        should_cache = not any("checkpoint" in str(e).lower() or "not installed" in str(e).lower() for e in res_errors)
        if should_cache:
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to write cache file: {e}")

        JOB_PROGRESS[job_id] = {"stage": "completed", "percent": 100}

        # Clean up temporary uploaded file
        try:
            dest_path.unlink()
        except Exception:
            pass

        return JSONResponse(content=result)
    except Exception as e:
        logger.exception("Unexpected error during analysis")
        JOB_PROGRESS[job_id] = {"stage": "error", "percent": 100}
        try:
            dest_path.unlink()
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={
                "module": "audio_forensics",
                "version": "1.0",
                "evidence_file": {"name": file.filename or "unknown", "sha256": file_sha256, "size_bytes": total_bytes, "type": "audio"},
                "analyzed_at": "",
                "verdict": "inconclusive",
                "overall_confidence": 0.0,
                "findings": [],
                "artifacts_dir": str(ARTIFACT_DIR),
                "errors": [f"Server analysis error: {str(e)}"],
                "raw_metrics": {},
            }
        )
