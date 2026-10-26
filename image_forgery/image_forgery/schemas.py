"""
Pydantic schemas for the image_forgery forensic module.
Strictly follows the PS-05 Digital Evidence Verification Platform integration contract.
Single Deep Engine: TruFor + Classical Forensic Suite.
"""

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class VerdictEnum(str, Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"
    LIKELY_TAMPERED = "likely_tampered"
    INCONCLUSIVE = "inconclusive"


class SeverityEnum(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingLocation(BaseModel):
    region: Optional[List[int]] = Field(
        default=None,
        description="Image bounding box in [x, y, w, h] format relative to original pixels."
    )
    frame_range: Optional[List[int]] = Field(
        default=None,
        description="Optional frame range [start, end] for video."
    )
    time_range_sec: Optional[List[float]] = Field(
        default=None,
        description="Optional time range [start, end] in seconds."
    )
    metadata_field: Optional[str] = Field(
        default=None,
        description="Name of metadata field if finding is metadata-specific."
    )


class Finding(BaseModel):
    id: str = Field(..., description="Unique finding identifier (e.g., 'FIND-001')")
    check: str = Field(..., description="Forensic check identifier, e.g. 'TRUFOR', 'ELA', 'METADATA_SOFTWARE'")
    severity: SeverityEnum = Field(..., description="Severity level: info, low, medium, high")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this finding (0.0 - 1.0)")
    description: str = Field(..., description="Human-readable description for non-technical officers")
    location: Optional[FindingLocation] = Field(
        default=None,
        description="Location specifics (region, metadata field, etc.)"
    )
    evidence_artifacts: List[str] = Field(
        default_factory=list,
        description="Relative paths to generated evidence images/plots"
    )


class EvidenceFile(BaseModel):
    name: str = Field(..., description="Original filename")
    sha256: str = Field(..., description="Cryptographic SHA-256 hash of evidence file")
    size_bytes: int = Field(..., description="File size in bytes")
    type: str = Field(..., description="Detected MIME type / image container format")


class AnalysisResult(BaseModel):
    module: str = Field(default="image_forgery", description="Module identifier")
    version: str = Field(default="1.0", description="Module version")
    evidence_file: EvidenceFile = Field(..., description="Evidence file metadata")
    analyzed_at: str = Field(..., description="ISO-8601 UTC timestamp of analysis")
    verdict: VerdictEnum = Field(..., description="Forensic verdict")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in verdict")
    findings: List[Finding] = Field(default_factory=list, description="Forensic findings sorted by severity")
    artifacts_dir: str = Field(..., description="Relative path where heatmaps/plots are saved")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during execution")
    raw_metrics: dict[str, Any] = Field(default_factory=dict, description="Raw forensic numbers and execution details")


class AnalysisOptions(BaseModel):
    engines: List[str] = Field(
        default_factory=lambda: ["trufor", "metadata", "ela"],
        description="List of forensic engines to run. Options: trufor, ela, copy_move, metadata"
    )
    mask_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Binarization threshold for anomaly localization heatmaps"
    )
    max_side: int = Field(
        default=1024,
        ge=256,
        le=4096,
        description="Max side length for TruFor inference (resized proportionally, then mapped back)"
    )
    ela_quality: int = Field(
        default=90,
        ge=1,
        le=100,
        description="JPEG re-compression quality for Error Level Analysis"
    )
    min_region_area_frac: float = Field(
        default=0.005,
        ge=0.0001,
        le=0.5,
        description="Minimum region area fraction of image to be retained as a finding"
    )
