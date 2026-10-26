"""
FastAPI router for ai_image_detection module.
Prefix: /api/ai_image_detection
Endpoints:
  POST /api/ai_image_detection/analyze
  GET  /api/ai_image_detection/health
  GET  /api/ai_image_detection/artifacts/{filename}
"""

import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse

try:
    from .analyzer import analyze
except (ImportError, ValueError):
    from analyzer import analyze

MODULE_NAME = "ai_image_detection"
router = APIRouter(prefix=f"/api/{MODULE_NAME}", tags=[MODULE_NAME])

# Directory configuration via environment variables
MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", PROJECT_ROOT / "uploads"))

raw_art = os.environ.get("ARTIFACT_DIR")
if raw_art:
    art_path = Path(raw_art)
    if art_path.name != MODULE_NAME:
        art_path = art_path / MODULE_NAME
    ARTIFACT_DIR = art_path
else:
    ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / MODULE_NAME

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health", summary="Module Health Check")
async def health_check() -> Dict[str, str]:
    """Health check endpoint confirming module status and identifier."""
    return {"status": "ok", "module": MODULE_NAME}


@router.post("/analyze", summary="Analyze Image for AI Synthesis Artifacts")
async def analyze_evidence(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Accepts an uploaded image file (multipart/form-data) and returns standard forensic result.
    Chain-of-custody SHA-256 is computed and artifacts are stored locally.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file missing filename.")

    # Sanitize filename and create unique timestamped destination
    clean_filename = Path(file.filename).name.replace(" ", "_")
    target_filename = f"{int(time.time() * 1000)}_{clean_filename}"
    target_path = UPLOAD_DIR / target_filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
    finally:
        await file.close()

    # Execute forensic analysis
    try:
        result = analyze(str(target_path))
        return result
    except Exception as e:
        # Failsafe fallback (analyzer should catch internal errors, but protect API level)
        return {
            "module": MODULE_NAME,
            "version": "1.0",
            "evidence_file": {
                "name": file.filename,
                "sha256": "",
                "size_bytes": target_path.stat().st_size if target_path.exists() else 0,
                "type": file.content_type or "unknown",
            },
            "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": f"artifacts/{MODULE_NAME}",
            "errors": [f"API execution exception: {str(e)}"],
            "raw_metrics": {}
        }


@router.get("/artifacts/{filename:path}", summary="Retrieve Visual Evidence Artifact")
async def get_artifact(filename: str):
    """
    Serves forensic visual artifacts (e.g. crop-score heatmaps).
    Validates path traversal to prevent unauthorized directory access.
    """
    # Prevent directory traversal
    safe_name = Path(filename).name
    file_path = ARTIFACT_DIR / safe_name

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {safe_name}")

    # Determine media type
    ext = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".json": "application/json"
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)
