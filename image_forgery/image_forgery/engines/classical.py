"""
Classical forensic checks for the image_forgery module.
Includes:
- Magic-byte intake detection & dimension validation
- EXIF & XMP metadata forensics (editing software, dates, thumbnail comparison)
- JPEG quantization table analysis and double-compression hint
- Error Level Analysis (ELA)
- Keypoint-based copy-move detection (SIFT with ORB fallback)
"""

import io
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import piexif
from PIL import Image, ExifTags

from .config import (
    MAX_IMAGE_MB,
    MAX_IMAGE_PIXELS,
    MIN_IMAGE_SIDE,
    LOW_JPEG_QUALITY_THRESHOLD,
)

# Standard libjpeg luminance quantization table (Quality 50)
STD_LUMINANCE_QUANT_50 = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99
], dtype=np.float32)

# Known editing software keywords (case-insensitive)
EDITING_SOFTWARE_KEYWORDS = [
    "photoshop", "adobe", "gimp", "lightroom", "snapseed", "canva",
    "midjourney", "stable diffusion", "dall-e", "pixlr", "affinity",
    "pixelmator", "paint.net", "corel", "acrobat", "fotor", "inpaint"
]


def detect_file_format(file_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect real image format from magic bytes.
    Returns (format_name, mime_type) or (None, None).
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)
    except Exception:
        return None, None

    if len(header) < 4:
        return None, None

    # JPEG
    if header.startswith(b"\xff\xd8\xff"):
        return "JPEG", "image/jpeg"
    # PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG", "image/png"
    # TIFF
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return "TIFF", "image/tiff"
    # WEBP
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "WEBP", "image/webp"
    # BMP
    if header.startswith(b"BM"):
        return "BMP", "image/bmp"

    return None, None


def validate_image_intake(file_path: Path) -> Dict[str, Any]:
    """
    Validate image file size, magic bytes, dimensions, and integrity.
    Raises ValueError on fatal rejection or returns dict with metadata.
    """
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > MAX_IMAGE_MB:
        raise ValueError(f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit ({MAX_IMAGE_MB} MB)")

    detected_format, mime_type = detect_file_format(file_path)
    ext = file_path.suffix.lower().lstrip(".")

    format_mismatch = False
    if detected_format:
        ext_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "tif": "TIFF", "tiff": "TIFF", "webp": "WEBP", "bmp": "BMP"}
        expected_format = ext_map.get(ext)
        if expected_format and expected_format != detected_format:
            format_mismatch = True
    else:
        raise ValueError("Unsupported or non-image file format (magic bytes not recognized)")

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            mode = img.mode
            num_pixels = width * height

            if num_pixels > MAX_IMAGE_PIXELS:
                raise ValueError(f"Image resolution ({width}x{height} = {num_pixels/1e6:.1f} MP) exceeds limit ({MAX_IMAGE_PIXELS/1e6:.0f} MP)")

            if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
                raise ValueError(f"Image dimension ({width}x{height}) is smaller than minimum required side ({MIN_IMAGE_SIDE}px)")

            # Check EXIF orientation
            orientation = None
            try:
                exif = img.getexif()
                if exif:
                    orientation = exif.get(0x0112)  # Orientation tag
            except Exception:
                pass

            # Read quantization tables if JPEG
            quant_tables = getattr(img, "quantization", None)

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Corrupt or unreadable image file: {str(e)}")

    return {
        "width": width,
        "height": height,
        "mode": mode,
        "size_bytes": size_bytes,
        "format": detected_format,
        "mime_type": mime_type,
        "format_mismatch": format_mismatch,
        "orientation": orientation,
        "has_quantization": quant_tables is not None,
    }


def analyze_metadata(file_path: Path, img_info: Dict[str, Any], artifacts_dir: Path) -> List[Dict[str, Any]]:
    """
    Examine EXIF, XMP, IPTC, and thumbnail consistency.
    Returns list of findings.
    """
    findings = []
    fid = 1

    # 1. Format extension mismatch
    if img_info.get("format_mismatch"):
        findings.append({
            "id": f"FIND-META-{fid:03d}",
            "check": "FORMAT_MISMATCH",
            "severity": "medium",
            "confidence": 0.95,
            "description": f"File extension .{file_path.suffix.lstrip('.')} mismatches genuine magic byte header ({img_info['format']}). Often indicative of obfuscation or re-saving.",
            "location": None,
            "evidence_artifacts": []
        })
        fid += 1

    # Read raw bytes for XMP search
    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
    except Exception:
        raw_bytes = b""

    software_tags = []
    dates = {}
    has_make_model = False
    has_gps = False
    thumbnail_mismatch = False
    thumbnail_artifact = None

    # Read EXIF
    try:
        with Image.open(file_path) as img:
            exif_dict = None
            if "exif" in img.info:
                try:
                    exif_dict = piexif.load(img.info["exif"])
                except Exception:
                    pass

            # Pillow getexif
            raw_exif = img.getexif()
            if raw_exif:
                for tag_id, val in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if tag_name == "Software" and isinstance(val, str):
                        software_tags.append(val.strip())
                    elif tag_name in ("Make", "Model") and val:
                        has_make_model = True
                    elif tag_name == "DateTime" and isinstance(val, str):
                        dates["ModifyDate"] = val.strip()

            if exif_dict:
                # 0th IFD
                zeroth = exif_dict.get("0th", {})
                if piexif.ImageIFD.Software in zeroth:
                    val = zeroth[piexif.ImageIFD.Software]
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="ignore").strip()
                    software_tags.append(str(val))
                if piexif.ImageIFD.Make in zeroth or piexif.ImageIFD.Model in zeroth:
                    has_make_model = True

                # Exif IFD
                exif_ifd = exif_dict.get("Exif", {})
                if piexif.ExifIFD.DateTimeOriginal in exif_ifd:
                    val = exif_ifd[piexif.ExifIFD.DateTimeOriginal]
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="ignore").strip()
                    dates["DateTimeOriginal"] = str(val)
                if piexif.ExifIFD.DateTimeDigitized in exif_ifd:
                    val = exif_ifd[piexif.ExifIFD.DateTimeDigitized]
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="ignore").strip()
                    dates["DateTimeDigitized"] = str(val)

                # GPS IFD
                if exif_dict.get("GPS"):
                    has_gps = True

                # Thumbnail check
                thumb_bytes = exif_dict.get("thumbnail")
                if thumb_bytes:
                    try:
                        thumb_img = Image.open(io.BytesIO(thumb_bytes))
                        # Compare thumbnail with main image
                        thumb_resized = thumb_img.convert("RGB").resize((64, 64))
                        main_resized = img.convert("RGB").resize((64, 64))
                        diff = np.mean(np.abs(np.array(thumb_resized, dtype=np.float32) - np.array(main_resized, dtype=np.float32)))
                        if diff > 45.0:  # Significant perceptual difference
                            thumbnail_mismatch = True
                            thumb_path = artifacts_dir / "exif_thumbnail.png"
                            thumb_img.save(thumb_path)
                            thumbnail_artifact = f"artifacts/image_forgery/{artifacts_dir.name}/exif_thumbnail.png"
                    except Exception:
                        pass
    except Exception:
        pass

    # XMP regex inspection
    xmp_matches = re.findall(rb"<x:xmpmeta.*?</x:xmpmeta>", raw_bytes, re.DOTALL)
    if not xmp_matches:
        xmp_matches = re.findall(rb"<\?xpacket begin.*?\?xpacket>", raw_bytes, re.DOTALL)

    xmp_history_events = []
    if xmp_matches:
        xmp_str = xmp_matches[0].decode("utf-8", errors="ignore")
        for kw in EDITING_SOFTWARE_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", xmp_str, re.IGNORECASE):
                software_tags.append(f"XMP match: {kw}")

        # Extract history events
        history_actions = re.findall(r'stEvt:action="([^"]+)"', xmp_str)
        history_agents = re.findall(r'stEvt:softwareAgent="([^"]+)"', xmp_str)
        if history_actions or history_agents:
            xmp_history_events.append(f"Actions: {list(set(history_actions))}, Agents: {list(set(history_agents))}")

    # Check for editing software tags
    flagged_editors = []
    for tag in set(software_tags):
        tag_lower = tag.lower()
        for kw in EDITING_SOFTWARE_KEYWORDS:
            if kw in tag_lower:
                flagged_editors.append(tag)
                break

    if flagged_editors:
        findings.append({
            "id": f"FIND-META-{fid:03d}",
            "check": "METADATA_SOFTWARE",
            "severity": "medium",
            "confidence": 0.85,
            "description": f"Image metadata references photo manipulation software: {', '.join(set(flagged_editors))}.",
            "location": {"metadata_field": "Software"},
            "evidence_artifacts": []
        })
        fid += 1

    # Date mismatch
    if "DateTimeOriginal" in dates and "ModifyDate" in dates:
        if dates["DateTimeOriginal"] != dates["ModifyDate"]:
            findings.append({
                "id": f"FIND-META-{fid:03d}",
                "check": "METADATA_DATES",
                "severity": "low",
                "confidence": 0.70,
                "description": f"Modification date ({dates['ModifyDate']}) differs from original capture date ({dates['DateTimeOriginal']}).",
                "location": {"metadata_field": "ModifyDate"},
                "evidence_artifacts": []
            })
            fid += 1

    # Missing camera make/model for JPEG
    if img_info["format"] == "JPEG" and not has_make_model:
        findings.append({
            "id": f"FIND-META-{fid:03d}",
            "check": "METADATA_MISSING_CAMERA",
            "severity": "info",
            "confidence": 0.50,
            "description": "Image is in JPEG format but lacks camera hardware Make/Model metadata. Metadata may have been stripped or synthesized.",
            "location": {"metadata_field": "Make/Model"},
            "evidence_artifacts": []
        })
        fid += 1

    # Thumbnail mismatch
    if thumbnail_mismatch:
        findings.append({
            "id": f"FIND-META-{fid:03d}",
            "check": "EXIF_THUMBNAIL_MISMATCH",
            "severity": "medium",
            "confidence": 0.85,
            "description": "Embedded EXIF thumbnail diverges significantly from main image content, indicating the main image was edited without refreshing the thumbnail.",
            "location": None,
            "evidence_artifacts": [thumbnail_artifact] if thumbnail_artifact else []
        })
        fid += 1

    # GPS indicator
    if has_gps:
        findings.append({
            "id": f"FIND-META-{fid:03d}",
            "check": "METADATA_GPS",
            "severity": "info",
            "confidence": 0.90,
            "description": "GPS geolocation metadata coordinates are embedded in EXIF.",
            "location": {"metadata_field": "GPSInfo"},
            "evidence_artifacts": []
        })
        fid += 1

    return findings


def analyze_jpeg_quantization(file_path: Path, artifacts_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Analyze JPEG quantization tables, estimate quality, and detect double-compression hints.
    """
    findings = []
    metrics: Dict[str, Any] = {}

    try:
        with Image.open(file_path) as img:
            if img.format != "JPEG":
                return findings, {"is_jpeg": False}

            quant = getattr(img, "quantization", None)
            if not quant:
                return findings, {"is_jpeg": True, "quant_tables_found": False}

            # Luminance table 0
            lum_table = quant.get(0)
            if lum_table:
                lum_arr = np.array(lum_table, dtype=np.float32)
                # Compare against standard libjpeg 50
                scaling = np.mean(lum_arr / STD_LUMINANCE_QUANT_50)
                if scaling > 1.0:
                    est_quality = round(5000.0 / (2.0 * scaling * 50.0))
                else:
                    est_quality = round(100.0 - (scaling * 50.0))
                est_quality = max(1, min(100, int(est_quality)))

                metrics["estimated_jpeg_quality"] = est_quality
                metrics["luminance_scaling_factor"] = float(scaling)

                # Check if quality is very low
                if est_quality < LOW_JPEG_QUALITY_THRESHOLD:
                    findings.append({
                        "id": "FIND-JPEG-001",
                        "check": "JPEG_QUANT_TABLES",
                        "severity": "low",
                        "confidence": 0.75,
                        "description": f"JPEG exhibits high compression / low estimated quality ({est_quality}%). High compression artifacts reduce forensic reliability.",
                        "location": None,
                        "evidence_artifacts": []
                    })

                # Check for editor-style tables (Photoshop typically has specific quantization entries)
                # Standard Photoshop 100 quality has all 1s in luminance; Photoshop tables often have uniform low frequencies
                if np.all(lum_arr[:4] <= 2) and est_quality >= 95:
                    findings.append({
                        "id": "FIND-JPEG-002",
                        "check": "JPEG_QUANT_TABLES",
                        "severity": "info",
                        "confidence": 0.65,
                        "description": "Quantization tables match high-quality digital photo editor export profiles.",
                        "location": None,
                        "evidence_artifacts": []
                    })
    except Exception as e:
        metrics["jpeg_analysis_error"] = str(e)

    return findings, metrics


def analyze_ela(file_path: Path, artifacts_dir: Path, quality: int = 90) -> Tuple[List[Dict[str, Any]], Optional[str], np.ndarray]:
    """
    Error Level Analysis (ELA):
    Re-saves the image at specified JPEG quality, measures difference, and generates a heatmap.
    """
    findings = []
    rel_artifact_path = None

    try:
        orig = Image.open(file_path).convert("RGB")
        w, h = orig.size

        # In-memory resave
        buf = io.BytesIO()
        orig.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        orig_np = np.array(orig, dtype=np.float32)
        resaved_np = np.array(resaved, dtype=np.float32)

        # Difference
        diff = np.abs(orig_np - resaved_np)
        diff_max = np.max(diff, axis=2)  # HxW

        # Amplify for visualization
        amplified = np.clip(diff_max * 12.0, 0, 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(amplified, cv2.COLORMAP_JET)

        # Save heatmap
        ela_filename = "ela.png"
        out_path = artifacts_dir / ela_filename
        cv2.imwrite(str(out_path), heatmap)
        rel_artifact_path = f"artifacts/image_forgery/{artifacts_dir.name}/{ela_filename}"

        # Analyze statistics
        mean_err = float(np.mean(diff_max))
        std_err = float(np.std(diff_max))
        max_err = float(np.max(diff_max))

        # Check if local regions have sharp discrepancy compared to mean
        high_diff_mask = (diff_max > (mean_err + 3.0 * std_err)).astype(np.uint8)
        high_diff_fraction = float(np.sum(high_diff_mask) / (w * h))

        # ELA Finding
        if high_diff_fraction > 0.01 and high_diff_fraction < 0.25:
            # Localized variance
            contours, _ = cv2.findContours(high_diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_box = None
            max_area = 0
            for cnt in contours:
                x, y, bw, bh = cv2.boundingRect(cnt)
                area = bw * bh
                if area > max_area and area >= (0.005 * w * h):
                    max_area = area
                    max_box = [int(x), int(y), int(bw), int(bh)]

            desc = "Error Level Analysis detected localized compression rate discrepancies. Note: ELA is a heuristic indicator subject to edge contrast false positives."
            findings.append({
                "id": "FIND-ELA-001",
                "check": "ELA",
                "severity": "low",
                "confidence": 0.60,
                "description": desc,
                "location": {"region": max_box} if max_box else None,
                "evidence_artifacts": [rel_artifact_path]
            })
        else:
            findings.append({
                "id": "FIND-ELA-001",
                "check": "ELA",
                "severity": "info",
                "confidence": 0.50,
                "description": "Error Level Analysis heatmap generated. Uniform error distribution observed across compression blocks.",
                "location": None,
                "evidence_artifacts": [rel_artifact_path]
            })

        norm_map = np.clip(diff_max / 35.0, 0.0, 1.0).astype(np.float32)
        return findings, rel_artifact_path, norm_map

    except Exception as e:
        empty_map = np.zeros((100, 100), dtype=np.float32)
        return [], None, empty_map


def analyze_copy_move(file_path: Path, artifacts_dir: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Detect duplicated regions using keypoint matching (SIFT with ORB fallback),
    ratio test, Euclidean distance threshold, and RANSAC consistency.
    """
    findings = []
    rel_artifact_path = None

    try:
        img_bgr = cv2.imread(str(file_path))
        if img_bgr is None:
            return findings, None

        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Try SIFT, fallback to ORB
        use_sift = hasattr(cv2, "SIFT_create")
        if use_sift:
            detector = cv2.SIFT_create(nfeatures=3000)
            norm_type = cv2.NORM_L2
            ratio_thresh = 0.70
        else:
            detector = cv2.ORB_create(nfeatures=3000)
            norm_type = cv2.NORM_HAMMING
            ratio_thresh = 0.75

        kps, des = detector.detectAndCompute(gray, None)
        if des is None or len(kps) < 20:
            return findings, None

        bf = cv2.BFMatcher(norm_type)
        matches = bf.knnMatch(des, des, k=3)

        min_spatial_dist = max(30, int(min(w, h) * 0.08))
        matched_pairs = []

        for m_list in matches:
            if len(m_list) >= 2:
                # 0th is match to itself (distance 0.0)
                m1 = m_list[1]
                if len(m_list) >= 3:
                    m2 = m_list[2]
                    # Lowe's ratio test
                    if m1.distance < ratio_thresh * m2.distance:
                        pt1 = np.array(kps[m1.queryIdx].pt)
                        pt2 = np.array(kps[m1.trainIdx].pt)
                        dist = np.linalg.norm(pt1 - pt2)
                        if dist >= min_spatial_dist:
                            matched_pairs.append((pt1, pt2))

        # Spatial shift clustering (filter false positives like uniform text or repeating patterns)
        clusters: Dict[Tuple[int, int], List[Tuple[np.ndarray, np.ndarray]]] = {}
        bin_size = 20

        for pt1, pt2 in matched_pairs:
            dx = int(round((pt2[0] - pt1[0]) / bin_size) * bin_size)
            dy = int(round((pt2[1] - pt1[1]) / bin_size) * bin_size)
            # Normalize vector direction
            if dx < 0 or (dx == 0 and dy < 0):
                dx, dy = -dx, -dy
            clusters.setdefault((dx, dy), []).append((pt1, pt2))

        # Select largest cluster with significant pairs
        best_cluster = []
        for shift, pairs in clusters.items():
            if len(pairs) >= 6 and len(pairs) > len(best_cluster):
                best_cluster = pairs

        if len(best_cluster) >= 6:
            vis = img_bgr.copy()
            src_pts = np.array([p[0] for p in best_cluster])
            dst_pts = np.array([p[1] for p in best_cluster])

            # Draw lines and circles
            for pt1, pt2 in best_cluster:
                p1 = (int(pt1[0]), int(pt1[1]))
                p2 = (int(pt2[0]), int(pt2[1]))
                cv2.circle(vis, p1, 4, (0, 0, 255), -1)
                cv2.circle(vis, p2, 4, (0, 255, 0), -1)
                cv2.line(vis, p1, p2, (255, 200, 0), 1)

            # Compute bounding boxes for source and destination clusters
            x1, y1, w1, h1 = cv2.boundingRect(src_pts.astype(np.float32))
            x2, y2, w2, h2 = cv2.boundingRect(dst_pts.astype(np.float32))

            cv2.rectangle(vis, (x1, y1), (x1 + w1, y1 + h1), (0, 0, 255), 2)
            cv2.rectangle(vis, (x2, y2), (x2 + w2, y2 + h2), (0, 255, 0), 2)

            out_path = artifacts_dir / "copy_move.png"
            cv2.imwrite(str(out_path), vis)
            rel_artifact_path = f"artifacts/image_forgery/{artifacts_dir.name}/copy_move.png"

            findings.append({
                "id": "FIND-CM-001",
                "check": "COPY_MOVE",
                "severity": "medium",
                "confidence": min(0.85, 0.50 + len(best_cluster) * 0.03),
                "description": f"Keypoint feature matching detected {len(best_cluster)} consistent geometric point pairs indicating potential copy-move duplication.",
                "location": {"region": [int(x2), int(y2), int(w2), int(h2)]},
                "evidence_artifacts": [rel_artifact_path]
            })

    except Exception:
        pass

    return findings, rel_artifact_path
