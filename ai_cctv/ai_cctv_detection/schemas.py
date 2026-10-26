"""Pydantic models conforming to the PS-05 Forensic Integration Contract."""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


VerdictType = Literal["authentic", "suspicious", "likely_tampered", "inconclusive"]
SeverityType = Literal["info", "low", "medium", "high"]


class EvidenceFile(BaseModel):
    name: str = Field(..., description="File name of the evidence")
    sha256: str = Field(..., description="SHA-256 hash of the evidence file for chain of custody")
    size_bytes: int = Field(..., description="Size of file in bytes")
    type: str = Field(..., description="MIME type or file extension format")


class Location(BaseModel):
    region: Optional[List[int]] = Field(None, description="[x, y, w, h] pixel region for images/frames")
    frame_range: Optional[List[int]] = Field(None, description="[start_frame, end_frame] indices")
    time_range_sec: Optional[List[float]] = Field(None, description="[start_sec, end_sec] timestamps in video")
    metadata_field: Optional[str] = Field(None, description="Specific metadata tag if applicable")


class Finding(BaseModel):
    id: str = Field(..., description="Unique identifier for the finding")
    check: str = Field(..., description="Name of forensic check (e.g. clip_ai_probability, suspicious_segment, video_quality_gate)")
    severity: SeverityType = Field(..., description="Severity level: info, low, medium, high")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this finding between 0.0 and 1.0")
    description: str = Field(..., description="Plain English description for non-technical officers")
    location: Optional[Location] = Field(None, description="Location in frame, time range, or metadata")
    evidence_artifacts: List[str] = Field(default_factory=list, description="Relative paths to generated evidence images/plots")


class StandardResult(BaseModel):
    module: str = Field("ai_cctv_detection", description="Module identifier")
    version: str = Field("1.0", description="Module version")
    evidence_file: EvidenceFile = Field(..., description="Metadata and hash of evidence file")
    analyzed_at: str = Field(..., description="ISO-8601 UTC timestamp of analysis")
    verdict: VerdictType = Field(..., description="Forensic verdict")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence level 0.0 - 1.0")
    findings: List[Finding] = Field(default_factory=list, description="Forensic findings sorted by severity")
    artifacts_dir: str = Field(..., description="Relative path where heatmaps/plots are saved")
    errors: List[str] = Field(default_factory=list, description="Non-fatal errors or pipeline issues encountered")
    raw_metrics: Dict[str, Any] = Field(default_factory=dict, description="Raw forensic metrics and frame stats")


class HealthResponse(BaseModel):
    status: str = "ok"
    module: str = "ai_cctv_detection"


class ProgressResponse(BaseModel):
    job_id: str
    stage: str
    percent: int
