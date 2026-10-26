"""FastAPI APIRouter for the ai_cctv_detection forensic module.

Endpoints:
- POST /api/ai_cctv_detection/analyze
- GET  /api/ai_cctv_detection/health
- GET  /api/ai_cctv_detection/artifacts/{filename}
- GET  /api/ai_cctv_detection/progress/{job_id}
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .analyzer import analyze, compute_sha256
from .schemas import HealthResponse, ProgressResponse, StandardResult

router = APIRouter(prefix="/api/ai_cctv_detection", tags=["ai_cctv_detection"])

MODULE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts/ai_cctv_detection")).resolve()
CACHE_DIR = Path(os.getenv("CACHE_DIR", "cache")).resolve()

# 2 GB default upload limit
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_BYTES", 2 * 1024 * 1024 * 1024))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Job progress tracking
_JOB_PROGRESS: Dict[str, Dict[str, any]] = {}
_THREAD_POOL = ThreadPoolExecutor(max_workers=4)


def _compute_config_hash() -> str:
    """Compute combined hash of quality, thresholds, and calibration YAMLs."""
    hasher = hashlib.sha256()
    configs_dir = MODULE_DIR / "configs"
    for name in sorted(["quality.yaml", "thresholds.yaml", "calibration.yaml"]):
        p = configs_dir / name
        if p.is_file():
            hasher.update(p.read_bytes())
    return hasher.hexdigest()[:12]


@router.get("/health", response_model=HealthResponse)
def health():
    """Module health check endpoint."""
    return HealthResponse(status="ok", module="ai_cctv_detection")


@router.get("/progress/{job_id}", response_model=ProgressResponse)
def get_progress(job_id: str):
    """Poll analysis progress for a specific job."""
    if job_id not in _JOB_PROGRESS:
        return ProgressResponse(job_id=job_id, stage="Initializing", percent=0)
    info = _JOB_PROGRESS[job_id]
    return ProgressResponse(
        job_id=job_id,
        stage=info.get("stage", "Processing"),
        percent=info.get("percent", 0),
    )


@router.get("/artifacts/{filename}")
def get_artifact(filename: str):
    """Serve generated visual evidence artifacts (timeline plots, contact sheets)."""
    # Sanitize filename to prevent directory traversal
    clean_name = Path(filename).name
    file_path = ARTIFACT_DIR / clean_name
    if not file_path.is_file():
        # Also check fallback subfolder if relative path provided
        alt_path = Path("artifacts/ai_cctv_detection") / clean_name
        if alt_path.is_file():
            file_path = alt_path
        else:
            raise HTTPException(status_code=404, detail="Artifact file not found")

    media_type = "image/png"
    if clean_name.endswith(".jpg") or clean_name.endswith(".jpeg"):
        media_type = "image/jpeg"
    return FileResponse(file_path, media_type=media_type)


@router.post("/analyze", response_model=StandardResult)
async def analyze_video(
    file: UploadFile = File(...),
    job_id: Optional[str] = Query(None),
    tracking: bool = Query(False),
):
    """Upload CCTV video clip and receive standard forensic analysis result.

    Streams file to disk in chunks to avoid out-of-memory errors on large uploads.
    """
    active_job_id = job_id or str(uuid.uuid4())
    _JOB_PROGRESS[active_job_id] = {"stage": "Receiving upload stream", "percent": 5}

    safe_filename = Path(file.filename or "unknown_video.mp4").name
    dest_path = UPLOAD_DIR / f"{active_job_id}_{safe_filename}"

    # Stream upload in 1MB chunks to disk
    total_written = 0
    try:
        with open(dest_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):
                total_written += len(chunk)
                if total_written > MAX_UPLOAD_SIZE:
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeded maximum permitted limit of {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB",
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to stream upload: {str(e)}")
    finally:
        await file.close()

    _JOB_PROGRESS[active_job_id] = {"stage": "Hashing and checking cache", "percent": 15}

    # Cache lookup by file SHA-256 + config hash
    file_hash = compute_sha256(dest_path)
    cfg_hash = _compute_config_hash()
    cache_key = f"{file_hash}_{cfg_hash}_{tracking}"
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.is_file():
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                cached_data = json.load(cf)
            _JOB_PROGRESS[active_job_id] = {"stage": "Retrieved from forensic cache", "percent": 100}
            return StandardResult(**cached_data)
        except Exception:
            pass  # Fall back to fresh analysis

    def update_job_progress(stage: str, percent: int):
        _JOB_PROGRESS[active_job_id] = {"stage": stage, "percent": percent}

    options = {
        "tracking": tracking,
        "progress_callback": update_job_progress,
    }

    # Execute CPU/GPU intensive analysis in thread pool so async event loop stays responsive
    loop = asyncio.get_event_loop()
    result_dict = await loop.run_in_executor(
        _THREAD_POOL,
        lambda: analyze(str(dest_path), options=options),
    )

    # Save to local cache
    try:
        with open(cache_file, "w", encoding="utf-8") as cf:
            json.dump(result_dict, cf, indent=2)
    except Exception:
        pass

    _JOB_PROGRESS[active_job_id] = {"stage": "Analysis complete", "percent": 100}
    return StandardResult(**result_dict)
