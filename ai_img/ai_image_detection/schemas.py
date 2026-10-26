"""
Pydantic schemas adhering strictly to the PS-05 Standard Forensic Result Format.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class EvidenceFile(BaseModel):
    name: str = Field(..., description="Original filename of the submitted evidence")
    sha256: str = Field(..., description="Cryptographic SHA-256 hash for chain-of-custody verification")
    size_bytes: int = Field(..., description="File size in bytes")
    type: str = Field(..., description="MIME type or detected image format")


class Location(BaseModel):
    region: Optional[List[int]] = Field(None, description="Bounding region [x, y, w, h] in image space")
    frame_range: Optional[List[int]] = Field(None, description="Video frame range [start, end]")
    time_range_sec: Optional[List[float]] = Field(None, description="Audio/video timeline range [start, end]")
    metadata_field: Optional[str] = Field(None, description="Specific metadata field name if applicable")


class Finding(BaseModel):
    id: str = Field(..., description="Unique identifier for the finding")
    check: str = Field(
        ...,
        description="Forensic check identifier (e.g., 'UnivFD_fake_probability', 'provenance_AI_marker', 'photo_type_and_quality', 'multi_crop_consistency', 'image_too_small')"
    )
    severity: Literal["info", "low", "medium", "high"] = Field(
        ...,
        description="Severity classification of the forensic finding"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this specific finding (0.0 to 1.0)"
    )
    description: str = Field(
        ...,
        description="Plain-English explanation understandable by a non-technical law enforcement officer"
    )
    location: Optional[Location] = Field(
        default=None,
        description="Location within evidence where finding occurred"
    )
    evidence_artifacts: List[str] = Field(
        default_factory=list,
        description="Relative file paths to generated artifacts/plots supporting this finding"
    )


class ModuleResult(BaseModel):
    module: str = Field("ai_image_detection", description="Module identifier")
    version: str = Field("1.0", description="Module specification version")
    evidence_file: EvidenceFile = Field(..., description="Evidence file metadata and hash")
    analyzed_at: str = Field(..., description="ISO-8601 UTC timestamp of analysis")
    verdict: Literal["authentic", "suspicious", "likely_tampered", "inconclusive"] = Field(
        ...,
        description="Standard forensic verdict vocabulary"
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence rating (0.0 to 1.0)"
    )
    findings: List[Finding] = Field(
        default_factory=list,
        description="List of granular forensic findings"
    )
    artifacts_dir: str = Field(
        ...,
        description="Relative path where module visual artifacts/plots are stored"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any caught non-fatal errors or execution warnings"
    )
    raw_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed raw metrics and operational diagnostics for forensic records"
    )
