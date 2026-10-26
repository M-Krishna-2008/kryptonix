"""
Unified Gateway Server for the 4 AI Forensics Modules.
Acts as reverse proxy, static frontend host, async job runner, content validator, and health aggregator.
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add gateway dir to path for imports
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validator import validate_upload
from jobs import JobManager, UPLOAD_DIR

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gateway")

app = FastAPI(
    title="Unified AI Forensics Platform Gateway",
    description="Unified API gateway and reverse proxy for Audio, AI Image, Forgery, and CCTV forensics modules.",
    version="1.0.0"
)

# Gateway is same-origin with frontend, but allow local dev requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_manager = JobManager()

# Path configurations
CONFIG_FILE = BASE_DIR / "config" / "modules.json"
PORTS_FILE = BASE_DIR / "runtime" / "ports.json"
FRONTEND_DIR = BASE_DIR / "frontend"


def load_module_manifest() -> Dict[str, Any]:
    if not CONFIG_FILE.is_file():
        raise RuntimeError(f"Manifest not found: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_runtime_ports() -> Dict[str, int]:
    """Reads runtime assigned ports or defaults from modules.json."""
    manifest = load_module_manifest()
    ports = {}
    # Defaults from manifest
    for m in manifest.get("modules", []):
        ports[m["id"]] = m.get("default_port", 8000)

    # Runtime overrides if written by launcher
    if PORTS_FILE.is_file():
        try:
            with open(PORTS_FILE, "r", encoding="utf-8") as f:
                runtime = json.load(f)
                ports.update(runtime)
        except Exception as e:
            logger.warning(f"Failed to read runtime ports: {e}")

    return ports


def get_module_config(module_id: str) -> Optional[Dict[str, Any]]:
    manifest = load_module_manifest()
    for m in manifest.get("modules", []):
        if m["id"] == module_id:
            return m
    return None


def get_backend_base_url(module_id: str) -> str:
    ports = get_runtime_ports()
    port = ports.get(module_id)
    if not port:
        raise HTTPException(status_code=500, detail=f"No port configured for module {module_id}")
    return f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Middleware: Request ID & Structured Logging
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.time()
    
    # Store request_id in state
    request.state.request_id = request_id

    response = await call_next(request)
    duration_ms = int((time.time() - start_time) * 1000)
    response.headers["X-Request-ID"] = request_id

    # Exclude high-frequency static asset polls from verbose logging
    path = request.url.path
    if not (path.startswith("/css") or path.startswith("/js") or path.startswith("/assets") or path == "/favicon.ico"):
        logger.info(json.dumps({
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms
        }))

    return response


# ---------------------------------------------------------------------------
# Gateway Management Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def aggregated_health():
    """
    Polls all 4 module backends in parallel and aggregates health status.
    Returns: overall status (healthy/degraded/down) + per-module detail.
    """
    manifest = load_module_manifest()
    ports = get_runtime_ports()
    results = {}
    any_up = False
    all_up = True

    async def check_module(mod: Dict[str, Any]):
        mod_id = mod["id"]
        port = ports.get(mod_id, mod.get("default_port"))
        health_ep = mod.get("health_endpoint", "/health")
        target_url = f"http://127.0.0.1:{port}{health_ep}"
        start_t = time.time()
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(target_url)
                latency = round((time.time() - start_t) * 1000, 1)
                if resp.status_code == 200:
                    data = resp.json()
                    return mod_id, {
                        "status": "up",
                        "port": port,
                        "latency_ms": latency,
                        "response": data,
                        "display_name": mod.get("display_name")
                    }
                else:
                    return mod_id, {
                        "status": "down",
                        "port": port,
                        "latency_ms": latency,
                        "error": f"HTTP {resp.status_code}",
                        "display_name": mod.get("display_name")
                    }
        except Exception as e:
            return mod_id, {
                "status": "down",
                "port": port,
                "latency_ms": None,
                "error": str(e),
                "display_name": mod.get("display_name")
            }

    tasks = [check_module(m) for m in manifest.get("modules", [])]
    check_results = await asyncio.gather(*tasks)

    for mod_id, res in check_results:
        results[mod_id] = res
        if res["status"] == "up":
            any_up = True
        else:
            all_up = False

    overall = "healthy" if all_up else ("degraded" if any_up else "down")

    return {
        "status": overall,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "modules": results
    }


@app.get("/api/config")
async def get_client_config():
    """Returns sanitized manifest and module configurations for frontend initialization."""
    manifest = load_module_manifest()
    ports = get_runtime_ports()
    
    sanitized_modules = []
    for m in manifest.get("modules", []):
        mod_copy = dict(m)
        mod_copy["active_port"] = ports.get(m["id"], m.get("default_port"))
        sanitized_modules.append(mod_copy)

    return {
        "platform": manifest.get("platform", {}),
        "modules": sanitized_modules
    }


# ---------------------------------------------------------------------------
# Asynchronous Job Execution & Polling
# ---------------------------------------------------------------------------
@app.post("/api/jobs")
async def create_analysis_job(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    module_id: str = Form(...),
):
    """
    Submits a file for background asynchronous processing.
    Validates content headers, writes to temp storage, and launches execution.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    mod_cfg = get_module_config(module_id)
    if not mod_cfg:
        raise HTTPException(status_code=400, detail=f"Invalid module_id: {module_id}")

    # Read first 128 bytes to validate magic bytes
    header_bytes = await file.read(128)
    await file.seek(0)

    # Stream to temp file while computing SHA-256 and size
    temp_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload.bin').name}"
    dest_path = UPLOAD_DIR / temp_name

    hasher = hashlib.sha256()
    total_bytes = 0
    max_bytes = mod_cfg.get("max_upload_bytes", 500 * 1024 * 1024)

    try:
        with open(dest_path, "wb") as f_out:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeded maximum permitted limit of {max_bytes / (1024*1024):.0f} MB"
                    )
                hasher.update(chunk)
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to stream upload: {str(e)}")
    finally:
        await file.close()

    # Content signature validation
    is_valid, detected_mime, val_err = validate_upload(
        header_bytes=header_bytes,
        file_size=total_bytes,
        module_id=module_id,
        max_bytes=max_bytes
    )
    if not is_valid:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=val_err)

    file_sha256 = hasher.hexdigest()

    # Create tracked job
    job = await job_manager.create_job(
        module_id=module_id,
        filename=file.filename or "evidence.bin",
        file_sha256=file_sha256,
        file_size_bytes=total_bytes,
        temp_file_path=str(dest_path),
        request_id=request_id
    )

    base_url = get_backend_base_url(module_id)
    analyze_ep = mod_cfg.get("analyze_endpoint", "/analyze")
    target_url = f"{base_url}{analyze_ep}"

    prog_template = None
    if mod_cfg.get("progress_endpoint"):
        prog_template = f"{base_url}{mod_cfg['progress_endpoint']}"

    form_field = mod_cfg.get("form_field", "file")

    # Dispatch to background task
    background_tasks.add_task(
        job_manager.run_job,
        job.job_id,
        target_url,
        form_field,
        prog_template
    )

    return JSONResponse(status_code=202, content=job.to_dict())


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll status and progress of an active or completed forensic analysis job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Forensic job not found or expired.")
    return job.to_dict()


# ---------------------------------------------------------------------------
# Reverse Proxy Handlers for All 4 Modules
# ---------------------------------------------------------------------------
async def proxy_request_to_module(module_id: str, subpath: str, request: Request):
    """Generic streaming reverse proxy to backend module."""
    base_url = get_backend_base_url(module_id)
    mod_cfg = get_module_config(module_id)
    upstream_prefix = mod_cfg.get("upstream_prefix", "") if mod_cfg else ""

    # Build target upstream URL
    target_path = f"{upstream_prefix}/{subpath}".replace("//", "/")
    target_url = f"{base_url}{target_path}"

    query_params = dict(request.query_params)
    body = await request.body()
    headers = dict(request.headers)
    # Strip host header so target sees its own
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                params=query_params,
                content=body,
                headers=headers
            )
            # Forward headers, excluding Hop-by-hop headers
            forward_headers = {}
            for k, v in resp.headers.items():
                if k.lower() not in ("content-length", "content-encoding", "transfer-encoding"):
                    forward_headers[k] = v

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=forward_headers,
                media_type=resp.headers.get("content-type")
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Module '{module_id}' backend is offline or not responding on {base_url}."
        )
    except Exception as e:
        logger.exception(f"Error proxying request to {target_url}: {e}")
        raise HTTPException(status_code=502, detail=f"Bad Gateway proxying to {module_id}: {str(e)}")


@app.api_route("/api/aud/{subpath:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_aud(subpath: str, request: Request):
    return await proxy_request_to_module("ai_aud", subpath, request)


@app.api_route("/api/img/{subpath:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_img(subpath: str, request: Request):
    return await proxy_request_to_module("ai_img", subpath, request)


@app.api_route("/api/forgery/{subpath:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_forgery(subpath: str, request: Request):
    return await proxy_request_to_module("image_forgery", subpath, request)


@app.api_route("/api/cctv/{subpath:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_cctv(subpath: str, request: Request):
    return await proxy_request_to_module("ai_cctv", subpath, request)


# ---------------------------------------------------------------------------
# Static Frontend Serving
# ---------------------------------------------------------------------------
if FRONTEND_DIR.is_dir():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/")
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn
    ports = get_runtime_ports()
    port = int(os.environ.get("GATEWAY_PORT", 8080))
    logger.info(f"Starting Unified Gateway on 127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
