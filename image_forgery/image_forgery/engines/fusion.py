"""
Fusion, confidence gating, and verdict determination for single deep engine (TruFor)
corroborated by independent classical forensic checks.
Implements transparent rules without opaque black-box averaging.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .config import (
    AUTH_CONFIDENCE_CAP,
    BORDER_MARGIN_PIXELS,
    DEFAULT_CONF_THRESHOLD,
    DEFAULT_MASK_THRESHOLD,
    DEFAULT_MIN_REGION_AREA_FRAC,
    LOW_JPEG_QUALITY_THRESHOLD,
    MAX_BOX_ASPECT_RATIO,
    QUALITY_WARN_MAX_FILE_SIZE_KB,
    QUALITY_WARN_MIN_SHORT_SIDE_PX,
    RELIABILITY_MIN_SIDE,
    TAMPERED_CONFIDENCE_CAP,
    TRUFOR_AUTHENTIC_THRESHOLD,
    TRUFOR_HIGH_SCORE_THRESHOLD,
    TRUFOR_LOW_SCORE_THRESHOLD,
    TRUFOR_TAMPERED_THRESHOLD,
)


def get_region_quadrant_description(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> str:
    """Return a plain-English quadrant descriptor (e.g., 'top-right', 'center')."""
    cx = x + w / 2.0
    cy = y + h / 2.0
    horiz = "left" if cx < img_w * 0.35 else ("right" if cx > img_w * 0.65 else "center")
    vert = "top" if cy < img_h * 0.35 else ("bottom" if cy > img_h * 0.65 else "center")
    if horiz == "center" and vert == "center":
        return "center area"
    if horiz == "center":
        return f"{vert}-center area"
    if vert == "center":
        return f"{horiz}-center area"
    return f"{vert}-{horiz} area"


def binarize_and_extract_regions(
    anomaly_map: np.ndarray,
    confidence_map: Optional[np.ndarray],
    mask_threshold: float,
    min_area_frac: float,
    conf_threshold: float = DEFAULT_CONF_THRESHOLD
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Binarize TruFor anomaly map, down-weight unreliable areas using confidence map,
    apply morphology, run connected components, and filter by minimum area.
    """
    h, w = anomaly_map.shape[:2]
    total_pixels = h * w
    min_pixels = int(total_pixels * min_area_frac)

    # Effective anomaly map: mask regions where confidence is too low
    effective_map = anomaly_map.copy()
    if confidence_map is not None:
        low_conf = (confidence_map < conf_threshold)
        effective_map[low_conf] = 0.0

    # Binarize
    binary = (effective_map >= mask_threshold).astype(np.uint8) * 255

    # Morphology: 5x5 ellipse kernel (close holes, open noise)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    clean_mask = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_OPEN, kernel)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(clean_mask, connectivity=8)

    regions = []
    filtered_mask = np.zeros_like(clean_mask)

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_pixels:
            bx = int(stats[i, cv2.CC_STAT_LEFT])
            by = int(stats[i, cv2.CC_STAT_TOP])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])

            # Drop detection boxes that touch the image border or are very thin (aspect ratio > 1:15),
            # since they are usually edge artifacts from padding/interpolation.
            margin = BORDER_MARGIN_PIXELS
            touches_border = (bx <= margin) or (by <= margin) or (bx + bw >= w - margin) or (by + bh >= h - margin)

            aspect_ratio = max(bw, bh) / max(1.0, float(min(bw, bh)))
            is_very_thin = aspect_ratio > MAX_BOX_ASPECT_RATIO

            if touches_border or is_very_thin:
                continue

            mean_intensity = float(np.mean(anomaly_map[labels == i]))
            mean_conf = float(np.mean(confidence_map[labels == i])) if confidence_map is not None else 1.0

            filtered_mask[labels == i] = 255
            regions.append({
                "region": [bx, by, bw, bh],
                "area_px": int(area),
                "area_frac": float(area / total_pixels),
                "mean_intensity": mean_intensity,
                "mean_confidence": mean_conf,
                "label_id": i
            })

    return filtered_mask, regions


def compute_box_iou(box1: List[int], box2: List[int]) -> float:
    """Compute IoU between two bounding boxes [x, y, w, h]."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_w = max(0, xi2 - xi1)
    inter_h = max(0, yi2 - yi1)
    inter_area = inter_w * inter_h

    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return float(inter_area / union_area)


def fuse_single_engine_results(
    trufor_output: Optional[Any],
    classical_findings: List[Dict[str, Any]],
    image_info: Dict[str, Any],
    artifacts_dir: Path,
    file_path: Path,
    opts: Dict[str, Any]
) -> Tuple[str, float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Perform forensic reasoning for single deep model (TruFor) supported by classical checks.
    Returns (verdict, overall_confidence, findings, confidence_breakdown).
    """
    w = image_info["width"]
    h = image_info["height"]
    mask_thresh = opts.get("mask_threshold", DEFAULT_MASK_THRESHOLD)
    min_area_frac = opts.get("min_region_area_frac", DEFAULT_MIN_REGION_AREA_FRAC)

    findings: List[Dict[str, Any]] = list(classical_findings)
    finding_counter = len(findings) + 1

    trufor_regions: List[Dict[str, Any]] = []
    trufor_ran = False
    trufor_score = None

    if trufor_output is not None and trufor_output.anomaly_map is not None:
        trufor_ran = True
        trufor_score = trufor_output.global_score
        clean_m, trufor_regions = binarize_and_extract_regions(
            trufor_output.anomaly_map,
            trufor_output.confidence_map,
            mask_threshold=mask_thresh,
            min_area_frac=min_area_frac
        )

        # Save binary mask visualization
        vis_mask = cv2.applyColorMap(clean_m, cv2.COLORMAP_JET)
        cv2.imwrite(str(artifacts_dir / "trufor_mask.png"), vis_mask)

    # Check classical corroboration signals
    has_medium_metadata = any(
        f["severity"] in ("medium", "high") and f["check"].startswith("METADATA_")
        for f in findings
    )
    has_thumbnail_mismatch = any(f["check"] == "EXIF_THUMBNAIL_MISMATCH" for f in findings)
    has_format_mismatch = any(f["check"] == "FORMAT_MISMATCH" for f in findings)
    has_copy_move = any(f["check"] == "COPY_MOVE" for f in findings)

    # Check ELA hotspot overlap
    ela_finding = next((f for f in findings if f["check"] == "ELA" and f.get("location")), None)
    ela_region = ela_finding["location"]["region"] if (ela_finding and ela_finding.get("location")) else None

    corroborating_signals: List[str] = []
    if has_medium_metadata:
        corroborating_signals.append("Editing software traces in metadata")
    if has_thumbnail_mismatch:
        corroborating_signals.append("EXIF embedded thumbnail divergence")
    if has_format_mismatch:
        corroborating_signals.append("File extension and magic byte mismatch")
    if has_copy_move:
        corroborating_signals.append("Keypoint copy-move duplicate detection")

    # Generate findings for TruFor regions
    for reg in trufor_regions:
        rx, ry, rw, rh = reg["region"]
        quad = get_region_quadrant_description(rx, ry, rw, rh, w, h)
        area_pct = reg["area_frac"] * 100.0

        # Check if ELA overlaps this specific region
        ela_overlap = False
        if ela_region:
            iou = compute_box_iou(reg["region"], ela_region)
            if iou > 0.15:
                ela_overlap = True
                if "Overlapping ELA compression variance" not in corroborating_signals:
                    corroborating_signals.append("Overlapping ELA compression variance")

        is_corroborated = len(corroborating_signals) > 0

        desc = (
            f"TruFor neural transformer localized an anomaly in the {quad} "
            f"(spanning {area_pct:.1f}% of image, pixel confidence: {reg['mean_confidence']*100:.0f}%). "
        )
        if is_corroborated:
            desc += f"Supported by independent forensic evidence: {', '.join(corroborating_signals)}."
        else:
            desc += "Single-engine neural detection without independent classical corroboration."

        conf = min(0.85, 0.55 + reg["mean_intensity"] * 0.25)
        findings.append({
            "id": f"FIND-TRU-{finding_counter:03d}",
            "check": "TRUFOR",
            "severity": "high" if is_corroborated else "medium",
            "confidence": round(conf, 2),
            "description": desc,
            "location": {"region": reg["region"]},
            "evidence_artifacts": [f"artifacts/image_forgery/{artifacts_dir.name}/trufor_overlay.png"]
        })
        finding_counter += 1

    # Single-model disclosure finding
    findings.append({
        "id": f"FIND-INFO-{finding_counter:03d}",
        "check": "MODEL_ARCHITECTURE",
        "severity": "info",
        "confidence": 1.0,
        "description": "Analysis performed using a single deep learning model (TruFor transformer) combined with classical forensics. No multi-model consensus was evaluated.",
        "location": None,
        "evidence_artifacts": []
    })
    finding_counter += 1

    # Input-quality warning check (Requirement 5)
    quality_warnings: List[str] = []
    file_size_kb = (file_path.stat().st_size / 1024.0) if file_path.exists() else 0.0
    if file_size_kb < QUALITY_WARN_MAX_FILE_SIZE_KB:
        quality_warnings.append(f"file size under {QUALITY_WARN_MAX_FILE_SIZE_KB:.0f} KB ({file_size_kb:.1f} KB)")

    short_side = min(w, h)
    if short_side < QUALITY_WARN_MIN_SHORT_SIDE_PX:
        quality_warnings.append(f"short side under {QUALITY_WARN_MIN_SHORT_SIDE_PX} px ({short_side} px)")

    fmt = image_info.get("format", "").upper()
    est_q = image_info.get("estimated_jpeg_quality")
    if fmt == "WEBP":
        quality_warnings.append("WebP lossy compression")
    elif est_q is not None and est_q < LOW_JPEG_QUALITY_THRESHOLD:
        quality_warnings.append(f"heavy compression (estimated quality {est_q}%)")

    if quality_warnings:
        findings.append({
            "id": f"FIND-WARN-{finding_counter:03d}",
            "check": "INPUT_QUALITY_WARNING",
            "severity": "low",
            "confidence": 0.85,
            "description": f"Input Quality Notice: Image has {', '.join(quality_warnings)}. Forensic manipulation localization and anomaly heatmaps are less reliable on low-resolution or heavily compressed web media.",
            "location": None,
            "evidence_artifacts": []
        })
        finding_counter += 1

    # Verdict Rules (Requirements 1 & 2):
    # Base verdict primarily on TruFor global integrity score.
    # Three calibrated verdicts:
    # 1. Likely Authentic (score < TRUFOR_AUTHENTIC_THRESHOLD, default 0.35)
    # 2. Likely Manipulated (score > TRUFOR_TAMPERED_THRESHOLD, default 0.60)
    # 3. Inconclusive (score between 0.35 and 0.60, or if TruFor unavailable)
    # Classical signals (ELA, Copy-Move) act strictly as supporting evidence and NEVER alone push verdict to suspicious.

    has_trufor_region = len(trufor_regions) > 0

    confidence_breakdown: Dict[str, Any] = {
        "single_deep_engine": "TruFor",
        "has_trufor_region": has_trufor_region,
        "trufor_regions_count": len(trufor_regions),
        "trufor_global_score": trufor_score,
        "corroborating_signals": corroborating_signals,
        "quality_warnings": quality_warnings,
        "thresholds": {
            "authentic_threshold": TRUFOR_AUTHENTIC_THRESHOLD,
            "tampered_threshold": TRUFOR_TAMPERED_THRESHOLD
        }
    }

    if trufor_score is not None:
        if trufor_score > TRUFOR_TAMPERED_THRESHOLD:
            verdict = "likely_tampered"
            base_conf = 0.70 + min(0.15, (trufor_score - TRUFOR_TAMPERED_THRESHOLD) * 0.4)
            if len(corroborating_signals) > 0:
                base_conf += 0.05
            if quality_warnings:
                base_conf -= 0.10
            overall_confidence = min(TAMPERED_CONFIDENCE_CAP, max(0.55, round(base_conf, 2)))
            confidence_breakdown["summary"] = f"TruFor global anomaly score ({trufor_score:.3f}) exceeds tampering threshold ({TRUFOR_TAMPERED_THRESHOLD})"

        elif trufor_score < TRUFOR_AUTHENTIC_THRESHOLD:
            verdict = "authentic"
            base_conf = 0.65 + min(0.10, (TRUFOR_AUTHENTIC_THRESHOLD - trufor_score) * 0.3)
            if quality_warnings:
                base_conf -= 0.05
            overall_confidence = min(AUTH_CONFIDENCE_CAP, max(0.55, round(base_conf, 2)))
            confidence_breakdown["summary"] = f"TruFor global anomaly score ({trufor_score:.3f}) below authenticity threshold ({TRUFOR_AUTHENTIC_THRESHOLD})"

        else:
            verdict = "inconclusive"
            overall_confidence = 0.50
            confidence_breakdown["summary"] = f"TruFor global score ({trufor_score:.3f}) in inconclusive range [{TRUFOR_AUTHENTIC_THRESHOLD}, {TRUFOR_TAMPERED_THRESHOLD}]"
    else:
        verdict = "inconclusive"
        overall_confidence = 0.50
        confidence_breakdown["summary"] = "Inconclusive: TruFor deep engine output unavailable"

    # Sort findings by severity: high -> medium -> low -> info
    sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (sev_rank.get(f["severity"], 4), -f["confidence"]))

    # Generate annotated.png with numbered bounding boxes
    generate_annotated_image(file_path, findings, artifacts_dir)

    return verdict, round(overall_confidence, 2), findings, confidence_breakdown


def generate_annotated_image(image_path: Path, findings: List[Dict[str, Any]], artifacts_dir: Path) -> Optional[str]:
    """Draw labeled bounding boxes on image matching finding locations."""
    try:
        with Image.open(image_path) as orig:
            annotated = orig.convert("RGB")
            draw = ImageDraw.Draw(annotated)
            w, h = annotated.size

            box_idx = 1
            for f in findings:
                loc = f.get("location")
                if loc and loc.get("region"):
                    rx, ry, rw, rh = loc["region"]
                    rx = max(0, min(w - 1, rx))
                    ry = max(0, min(h - 1, ry))
                    x2 = max(0, min(w - 1, rx + rw))
                    y2 = max(0, min(h - 1, ry + rh))

                    sev = f.get("severity", "info")
                    if sev == "high":
                        box_color = (239, 68, 68)     # Red
                    elif sev == "medium":
                        box_color = (245, 158, 11)   # Amber
                    elif sev == "low":
                        box_color = (59, 130, 246)    # Blue
                    else:
                        box_color = (16, 185, 129)    # Emerald

                    for offset in range(3):
                        draw.rectangle(
                            [rx - offset, ry - offset, x2 + offset, y2 + offset],
                            outline=box_color
                        )

                    label_text = f"[{box_idx}] {f['id']}"
                    badge_w = len(label_text) * 8 + 10
                    badge_h = 18
                    draw.rectangle(
                        [rx, max(0, ry - badge_h), rx + badge_w, max(0, ry)],
                        fill=box_color
                    )
                    draw.text(
                        (rx + 4, max(0, ry - badge_h) + 2),
                        label_text,
                        fill=(255, 255, 255)
                    )
                    box_idx += 1

            out_path = artifacts_dir / "annotated.png"
            annotated.save(out_path)
            return f"artifacts/image_forgery/{artifacts_dir.name}/annotated.png"

    except Exception:
        return None
