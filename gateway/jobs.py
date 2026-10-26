"""
Asynchronous Job & Task Management for long-running forensic analyses.
Tracks job state, background execution, progress polling, and automatic cleanup.
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger("gateway.jobs")

UPLOAD_DIR = Path("runtime/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ForensicJob:
    job_id: str
    request_id: str
    module_id: str
    filename: str
    file_sha256: str
    file_size_bytes: int
    status: str = "pending"  # pending, running, completed, failed
    stage: str = "Job queued"
    percent: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    temp_file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "request_id": self.request_id,
            "module_id": self.module_id,
            "filename": self.filename,
            "file_sha256": self.file_sha256,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "stage": self.stage,
            "percent": self.percent,
            "created_at": datetime.fromtimestamp(self.created_at, timezone.utc).isoformat(),
            "updated_at": datetime.fromtimestamp(self.updated_at, timezone.utc).isoformat(),
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, ForensicJob] = {}
        self.lock = asyncio.Lock()

    def get_job(self, job_id: str) -> Optional[ForensicJob]:
        return self.jobs.get(job_id)

    async def create_job(
        self,
        module_id: str,
        filename: str,
        file_sha256: str,
        file_size_bytes: int,
        temp_file_path: str,
        request_id: str,
    ) -> ForensicJob:
        job_id = str(uuid.uuid4())
        job = ForensicJob(
            job_id=job_id,
            request_id=request_id,
            module_id=module_id,
            filename=filename,
            file_sha256=file_sha256,
            file_size_bytes=file_size_bytes,
            status="pending",
            stage="Initializing analysis job",
            percent=5,
            temp_file_path=temp_file_path,
        )
        async with self.lock:
            self.jobs[job_id] = job
            self._cleanup_old_jobs()
        return job

    def _cleanup_old_jobs(self, ttl_seconds: int = 3600):
        """Purge jobs older than TTL to prevent memory accumulation."""
        now = time.time()
        expired = [
            jid for jid, j in self.jobs.items()
            if now - j.updated_at > ttl_seconds and j.status in ("completed", "failed")
        ]
        for jid in expired:
            j = self.jobs.pop(jid, None)
            if j and j.temp_file_path:
                try:
                    p = Path(j.temp_file_path)
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass

    async def run_job(
        self,
        job_id: str,
        target_url: str,
        form_field: str,
        progress_url_template: Optional[str] = None
    ):
        """
        Executes analysis against the target backend module.
        Continuously updates progress until finished.
        """
        job = self.jobs.get(job_id)
        if not job:
            return

        job.status = "running"
        job.stage = "Transmitting evidence to module"
        job.percent = 15
        job.updated_at = time.time()

        temp_p = Path(job.temp_file_path) if job.temp_file_path else None
        if not temp_p or not temp_p.is_file():
            job.status = "failed"
            job.error = "Evidence file not found in gateway storage."
            job.updated_at = time.time()
            return

        start_time = time.time()

        # Background progress poller if module supports it
        stop_polling = asyncio.Event()

        async def poll_module_progress():
            if not progress_url_template:
                return
            prog_url = progress_url_template.replace("{job_id}", job.job_id)
            async with httpx.AsyncClient(timeout=3.0) as client:
                while not stop_polling.is_set():
                    try:
                        await asyncio.sleep(0.8)
                        if stop_polling.is_set():
                            break
                        resp = await client.get(prog_url)
                        if resp.status_code == 200:
                            data = resp.json()
                            p_val = data.get("percent")
                            s_val = data.get("stage")
                            if p_val is not None:
                                job.percent = max(job.percent, min(95, int(p_val)))
                            if s_val:
                                job.stage = str(s_val)
                            job.updated_at = time.time()
                    except Exception:
                        pass

        poller_task = None
        if progress_url_template:
            poller_task = asyncio.create_task(poll_module_progress())

        try:
            # Send file to backend
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(temp_p, "rb") as f:
                    files = {form_field: (job.filename, f, "application/octet-stream")}
                    params = {}
                    if job.module_id == "ai_cctv":
                        params["job_id"] = job.job_id

                    resp = await client.post(target_url, files=files, params=params)

                stop_polling.set()
                if poller_task:
                    await asyncio.gather(poller_task, return_exceptions=True)

                if resp.status_code == 200:
                    result = resp.json()
                    job.status = "completed"
                    job.stage = "Analysis completed"
                    job.percent = 100
                    job.result = result
                    job.updated_at = time.time()

                    duration_ms = int((time.time() - start_time) * 1000)
                    verdict = result.get("verdict", "unknown")
                    logger.info(json.dumps({
                        "event": "job_completed",
                        "request_id": job.request_id,
                        "job_id": job.job_id,
                        "module": job.module_id,
                        "file_sha256": job.file_sha256,
                        "duration_ms": duration_ms,
                        "verdict": verdict,
                    }))
                else:
                    err_msg = f"Module backend returned error HTTP {resp.status_code}: {resp.text[:200]}"
                    job.status = "failed"
                    job.stage = "Analysis failed"
                    job.percent = 100
                    job.error = err_msg
                    job.updated_at = time.time()
                    logger.error(f"Job {job_id} failed: {err_msg}")

        except Exception as e:
            stop_polling.set()
            if poller_task:
                await asyncio.gather(poller_task, return_exceptions=True)
            job.status = "failed"
            job.stage = "Error during analysis execution"
            job.percent = 100
            job.error = f"Execution error: {str(e)}"
            job.updated_at = time.time()
            logger.exception(f"Job {job_id} exception: {e}")

        finally:
            # Always delete raw evidence temp upload after job finishes
            try:
                if temp_p and temp_p.exists():
                    temp_p.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_p}: {e}")
