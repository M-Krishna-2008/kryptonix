"""
FastAPI router for the image_forgery module.
Prefix: /api/image_forgery
Implements all contractual endpoints, threadpool execution, path-traversal prevention,
and streaming uploads with hash-based storage.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

try:
    from .analyzer import analyze, get_available_engines_info
    from .engines.config import ARTIFACT_DIR, MAX_IMAGE_MB, MODULE_NAME, UPLOAD_DIR
except ImportError:
    from analyzer import analyze, get_available_engines_info
    from engines.config import ARTIFACT_DIR, MAX_IMAGE_MB, MODULE_NAME, UPLOAD_DIR

router = APIRouter(prefix=f"/api/{MODULE_NAME}", tags=[MODULE_NAME])

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODULE_ARTIFACTS_DIR = ARTIFACT_DIR / MODULE_NAME
MODULE_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health")
async def health_check():
    """Health check endpoint required by integration contract."""
    return {"status": "ok", "module": MODULE_NAME}


@router.get("/engines")
async def list_engines():
    """Optional endpoint detailing forensic engine capabilities and weights."""
    return get_available_engines_info()


@router.post("/analyze")
async def analyze_endpoint(
    file: UploadFile = File(..., description="Evidence image file"),
    options: Optional[str] = Form(None, description="JSON string of analysis options")
):
    """
    Upload and analyze evidence image.
    Streams upload to disk with size limiting, prevents filename tampering,
    and runs analysis asynchronously in threadpool.
    """
    parsed_options = None
    if options:
        try:
            parsed_options = json.loads(options)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON in options field: {str(e)}"
            )

    # Temporary file for streaming upload
    temp_upload = UPLOAD_DIR / f"temp_{os.urandom(8).hex()}.tmp"
    hasher = hashlib.sha256()
    total_bytes = 0
    max_bytes = MAX_IMAGE_MB * 1024 * 1024

    try:
        with open(temp_upload, "wb") as f_out:
            while chunk := await file.read(65536):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size ({MAX_IMAGE_MB} MB)"
                    )
                hasher.update(chunk)
                f_out.write(chunk)
    except Exception as e:
        if temp_upload.exists():
            temp_upload.unlink()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to receive file stream: {str(e)}"
        )

    file_sha256 = hasher.hexdigest().lower()
    orig_ext = Path(file.filename or "").suffix.lower()
    if not orig_ext or len(orig_ext) > 10:
        orig_ext = ".bin"

    final_upload_path = UPLOAD_DIR / f"{file_sha256}{orig_ext}"
    if not final_upload_path.exists():
        shutil.move(str(temp_upload), str(final_upload_path))
    else:
        temp_upload.unlink()

    # Offload heavy analysis to worker thread pool
    result = await run_in_threadpool(analyze, str(final_upload_path), parsed_options)
    # Restore original client filename in response metadata
    if file.filename:
        result["evidence_file"]["name"] = file.filename

    return JSONResponse(content=result)


@router.get("/artifacts/{filename:path}")
async def get_artifact(filename: str):
    """
    Serve generated artifact visual evidence.
    Enforces strict path traversal prevention via Path.resolve().
    """
    # Clean incoming path
    clean_rel = Path(filename.replace("\\", "/")).as_posix().lstrip("/")
    target_path = (MODULE_ARTIFACTS_DIR / clean_rel).resolve()
    base_dir = MODULE_ARTIFACTS_DIR.resolve()

    # Verify that target_path is within base_dir (block path traversal)
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Invalid artifact path traversal attempt."
        )

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact not found: {filename}"
        )

    media_type = "image/png"
    if target_path.suffix.lower() in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif target_path.suffix.lower() == ".json":
        media_type = "application/json"

    return FileResponse(path=str(target_path), media_type=media_type)
