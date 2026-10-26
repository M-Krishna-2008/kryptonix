"""
Core forensic orchestrator for the image_forgery module.
Single Deep Engine: TruFor (primary transformer) supported by classical forensic checks.
Implements the exact single entry point:
    def analyze(file_path: str, options: dict | None = None) -> dict
Never raises to the caller.
"""

import datetime
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .engines.base import EngineOutput
    from .engines.classical import (
        analyze_copy_move,
        analyze_ela,
        analyze_jpeg_quantization,
        analyze_metadata,
        validate_image_intake,
    )
    from .engines.config import (
        ARTIFACT_DIR,
        DEFAULT_ELA_QUALITY,
        DEFAULT_MASK_THRESHOLD,
        DEFAULT_MAX_SIDE,
        DEFAULT_MIN_REGION_AREA_FRAC,
        MODULE_NAME,
        MODULE_ROOT,
        TRUFOR_HIGH_SCORE_THRESHOLD,
        TRUFOR_LOW_SCORE_THRESHOLD,
    )
    from .engines.fusion import fuse_single_engine_results
    from .engines.trufor import TruForEngine
    from .schemas import AnalysisOptions, AnalysisResult, EvidenceFile, Finding, SeverityEnum, VerdictEnum
except ImportError:
    from engines.base import EngineOutput
    from engines.classical import (
        analyze_copy_move,
        analyze_ela,
        analyze_jpeg_quantization,
        analyze_metadata,
        validate_image_intake,
    )
    from engines.config import (
        ARTIFACT_DIR,
        DEFAULT_ELA_QUALITY,
        DEFAULT_MASK_THRESHOLD,
        DEFAULT_MAX_SIDE,
        DEFAULT_MIN_REGION_AREA_FRAC,
        MODULE_NAME,
        MODULE_ROOT,
        TRUFOR_HIGH_SCORE_THRESHOLD,
        TRUFOR_LOW_SCORE_THRESHOLD,
    )
    from engines.fusion import fuse_single_engine_results
    from engines.trufor import TruForEngine
    from schemas import AnalysisOptions, AnalysisResult, EvidenceFile, Finding, SeverityEnum, VerdictEnum

# Global lock ensuring sequential execution on the host machine
_ANALYSIS_LOCK = threading.Lock()


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of file for chain-of-custody tracking."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def get_available_engines_info() -> Dict[str, Dict[str, Any]]:
    """Return status, availability, and licensing notes for supported engines."""
    trufor = TruForEngine()

    manifest_path = MODULE_ROOT / "models" / "MANIFEST.json"
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            pass

    t_avail, t_reason = trufor.check_available()

    return {
        "trufor": {
            "available": t_avail,
            "reason": t_reason,
            "weights_sha256": manifest.get("trufor", {}).get("sha256"),
            "license_note": manifest.get("trufor", {}).get("license_note", "Informational and nonprofit use only")
        },
        "ela": {
            "available": True,
            "reason": "Classical Error Level Analysis (built-in)",
            "weights_sha256": None,
            "license_note": "Open source"
        },
        "copy_move": {
            "available": True,
            "reason": "Classical keypoint matching (OpenCV SIFT/ORB)",
            "weights_sha256": None,
            "license_note": "Open source"
        },
        "metadata": {
            "available": True,
            "reason": "EXIF/XMP parsing (Pillow + piexif)",
            "weights_sha256": None,
            "license_note": "Open source"
        }
    }


def analyze(file_path: str, options: dict | None = None) -> dict:
    """
    Standard entry point for image_forgery module.
    Analyzes digital evidence and returns Standard Result Format JSON.
    Never raises an exception to caller.
    """
    total_start_time = time.time()
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    p_file = Path(file_path)

    # Base evidence file placeholder
    evidence_file_dict = {
        "name": p_file.name if p_file.exists() else str(file_path),
        "sha256": "",
        "size_bytes": 0,
        "type": "application/octet-stream"
    }

    errors: List[str] = []
    raw_metrics: Dict[str, Any] = {
        "python_version": sys.version,
        "platform": sys.platform,
        "total_runtime_sec": 0.0,
        "engines": {}
    }

    # Record PyTorch / CUDA version if torch installed
    try:
        import torch
        raw_metrics["torch_version"] = torch.__version__
        raw_metrics["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            raw_metrics["cuda_device_name"] = torch.cuda.get_device_name(0)
    except Exception:
        raw_metrics["torch_version"] = "not_installed"
        raw_metrics["cuda_available"] = False

    # Check file existence
    if not p_file.exists() or not p_file.is_file():
        errors.append(f"Evidence file does not exist or is not a file: {file_path}")
        return {
            "module": MODULE_NAME,
            "version": "1.0",
            "evidence_file": evidence_file_dict,
            "analyzed_at": now_utc,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": "",
            "errors": errors,
            "raw_metrics": raw_metrics
        }

    # Compute SHA-256 and size
    try:
        file_sha256 = _compute_sha256(p_file)
        evidence_file_dict["sha256"] = file_sha256
        evidence_file_dict["size_bytes"] = p_file.stat().st_size
    except Exception as e:
        errors.append(f"Failed to read evidence file for SHA-256 calculation: {str(e)}")
        return {
            "module": MODULE_NAME,
            "version": "1.0",
            "evidence_file": evidence_file_dict,
            "analyzed_at": now_utc,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": "",
            "errors": errors,
            "raw_metrics": raw_metrics
        }

    # Setup artifacts directory: ARTIFACT_DIR / image_forgery / sha256[:12]
    hash_prefix = file_sha256[:12]
    artifacts_path = ARTIFACT_DIR / MODULE_NAME / hash_prefix
    artifacts_path.mkdir(parents=True, exist_ok=True)
    rel_artifacts_dir = f"artifacts/{MODULE_NAME}/{hash_prefix}"

    # Parse and clamp options with pydantic
    try:
        opts_obj = AnalysisOptions(**(options or {}))
        opts_dict = opts_obj.model_dump()
    except Exception as e:
        opts_dict = AnalysisOptions().model_dump()
        errors.append(f"Options parsing error, using defaults: {str(e)}")

    raw_metrics["thresholds_used"] = {
        "mask_threshold": opts_dict["mask_threshold"],
        "max_side": opts_dict["max_side"],
        "ela_quality": opts_dict["ela_quality"],
        "min_region_area_frac": opts_dict["min_region_area_frac"],
        "trufor_authentic_threshold": TRUFOR_LOW_SCORE_THRESHOLD,
        "trufor_tampered_threshold": TRUFOR_HIGH_SCORE_THRESHOLD
    }

    # 1. Intake validation & magic byte check
    try:
        image_info = validate_image_intake(p_file)
        evidence_file_dict["type"] = image_info["mime_type"]
        raw_metrics["image"] = {
            "width": image_info["width"],
            "height": image_info["height"],
            "format": image_info["format"],
            "mime_type": image_info["mime_type"],
            "orientation": image_info["orientation"]
        }
    except Exception as e:
        errors.append(f"Intake validation failure: {str(e)}")
        res = {
            "module": MODULE_NAME,
            "version": "1.0",
            "evidence_file": evidence_file_dict,
            "analyzed_at": now_utc,
            "verdict": "inconclusive",
            "overall_confidence": 0.0,
            "findings": [],
            "artifacts_dir": rel_artifacts_dir,
            "errors": errors,
            "raw_metrics": raw_metrics
        }
        try:
            with open(artifacts_path / "result.json", "w", encoding="utf-8") as rf:
                json.dump(res, rf, indent=2)
        except Exception:
            pass
        return res

    # Acquire sequential execution lock
    with _ANALYSIS_LOCK:
        try:
            all_findings: List[Dict[str, Any]] = []
            selected_engines = opts_dict.get("engines", [])

            # Classical checks
            # A. Metadata Forensics
            if "metadata" in selected_engines:
                t_m0 = time.time()
                meta_findings = analyze_metadata(p_file, image_info, artifacts_path)
                all_findings.extend(meta_findings)
                raw_metrics["engines"]["metadata"] = {
                    "available": True,
                    "applicable": True,
                    "findings_count": len(meta_findings),
                    "runtime_sec": round(time.time() - t_m0, 4)
                }

            # B. JPEG Quantization Analysis
            if image_info["format"] == "JPEG":
                quant_findings, quant_metrics = analyze_jpeg_quantization(p_file, artifacts_path)
                all_findings.extend(quant_findings)
                if "estimated_jpeg_quality" in quant_metrics:
                    image_info["estimated_jpeg_quality"] = quant_metrics["estimated_jpeg_quality"]
                raw_metrics["image"]["jpeg_metrics"] = quant_metrics

            # C. Error Level Analysis (ELA)
            if "ela" in selected_engines:
                t_e0 = time.time()
                ela_findings, ela_art, _ = analyze_ela(p_file, artifacts_path, quality=opts_dict["ela_quality"])
                all_findings.extend(ela_findings)
                raw_metrics["engines"]["ela"] = {
                    "available": True,
                    "applicable": True,
                    "artifact": ela_art,
                    "runtime_sec": round(time.time() - t_e0, 4)
                }

            # D. Keypoint Copy-Move
            if "copy_move" in selected_engines:
                t_cm0 = time.time()
                cm_findings, cm_art = analyze_copy_move(p_file, artifacts_path)
                all_findings.extend(cm_findings)
                raw_metrics["engines"]["copy_move"] = {
                    "available": True,
                    "applicable": True,
                    "artifact": cm_art,
                    "runtime_sec": round(time.time() - t_cm0, 4)
                }

            # Deep Engine: TruFor
            trufor_out: Optional[EngineOutput] = None
            if "trufor" in selected_engines:
                trufor = TruForEngine()
                t_avail, t_reason = trufor.check_available()
                t_appl, t_appl_reason = trufor.applicable(image_info)
                engines_info = get_available_engines_info()
                raw_metrics["engines"]["trufor"] = {
                    "available": t_avail,
                    "applicable": t_appl,
                    "reason": t_reason if not t_avail else t_appl_reason,
                    "weights_sha256": engines_info.get("trufor", {}).get("weights_sha256")
                }

                if t_avail and t_appl:
                    trufor_out = trufor.run(p_file, artifacts_path, opts_dict)
                    raw_metrics["engines"]["trufor"].update({
                        "global_score": trufor_out.global_score,
                        "score_is_native": trufor_out.score_is_native,
                        "runtime_sec": round(trufor_out.runtime_sec, 4),
                        "device": trufor_out.device,
                        "scale_factor": round(trufor_out.scale_factor, 4)
                    })
                    if "error" in trufor_out.extras and trufor_out.extras["error"]:
                        errors.append(f"TruFor engine warning/error: {trufor_out.extras['error']}")
                else:
                    raw_metrics["engines"]["trufor"]["skipped"] = True

            # Perform single deep engine fusion and verdict determination
            verdict, overall_confidence, findings, conf_breakdown = fuse_single_engine_results(
                trufor_out,
                all_findings,
                image_info,
                artifacts_path,
                p_file,
                opts_dict
            )

            raw_metrics["confidence_breakdown"] = conf_breakdown
            raw_metrics["total_runtime_sec"] = round(time.time() - total_start_time, 4)

            # Assemble Standard Result
            result_data = {
                "module": MODULE_NAME,
                "version": "1.0",
                "evidence_file": evidence_file_dict,
                "analyzed_at": now_utc,
                "verdict": verdict,
                "overall_confidence": overall_confidence,
                "findings": findings,
                "artifacts_dir": rel_artifacts_dir,
                "errors": errors,
                "raw_metrics": raw_metrics
            }

            # Save chain of custody result.json
            try:
                with open(artifacts_path / "result.json", "w", encoding="utf-8") as rf:
                    json.dump(result_data, rf, indent=2)
            except Exception as e:
                errors.append(f"Failed to write chain of custody result.json: {str(e)}")

            return result_data

        except Exception as e:
            errors.append(f"Unexpected analysis failure: {str(e)}")
            raw_metrics["total_runtime_sec"] = round(time.time() - total_start_time, 4)
            return {
                "module": MODULE_NAME,
                "version": "1.0",
                "evidence_file": evidence_file_dict,
                "analyzed_at": now_utc,
                "verdict": "inconclusive",
                "overall_confidence": 0.0,
                "findings": [],
                "artifacts_dir": rel_artifacts_dir,
                "errors": errors,
                "raw_metrics": raw_metrics
            }
