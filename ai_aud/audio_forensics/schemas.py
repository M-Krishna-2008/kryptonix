from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceFile(BaseModel):
    name: str
    sha256: str
    size_bytes: int
    type: str


class FindingLocation(BaseModel):
    region: Optional[List[int]] = None           # [x, y, w, h] for images
    frame_range: Optional[List[int]] = None      # [start, end] for video
    time_range_sec: Optional[List[float]] = None # [start, end] for audio/video
    metadata_field: Optional[str] = None         # metadata field name


class Finding(BaseModel):
    id: str
    check: str
    severity: str = Field(..., description="'info' | 'low' | 'medium' | 'high'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: str
    location: Optional[FindingLocation] = None
    evidence_artifacts: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    module: str = "audio_forensics"
    version: str = "1.0"
    evidence_file: EvidenceFile
    analyzed_at: str
    verdict: str = Field(..., description="'authentic' | 'suspicious' | 'likely_tampered' | 'inconclusive'")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    findings: List[Finding]
    artifacts_dir: str
    errors: List[str] = Field(default_factory=list)
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    module: str


class ProgressResponse(BaseModel):
    job_id: str
    stage: str
    percent: int
