"""
Content validation using file magic bytes and signature analysis.
Decodes headers to detect actual media type instead of trusting file extensions.
"""

from typing import Tuple, Optional
from pathlib import Path


def detect_file_type(header: bytes) -> Optional[str]:
    """
    Examines the first 32-64 bytes of a file to determine its actual content type.
    Returns standard category (audio, image, video) or None.
    """
    if len(header) < 4:
        return None

    # JPEG: FF D8 FF
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # GIF: GIF87a or GIF89a
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"

    # WEBP: RIFF....WEBP
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return "image/webp"

    # BMP: BM
    if header.startswith(b"BM"):
        return "image/bmp"

    # TIFF: II*\x00 (little-endian) or MM\x00* (big-endian)
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return "image/tiff"

    # WAV: RIFF....WAVE
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
        return "audio/wav"

    # FLAC: fLaC
    if header.startswith(b"fLaC"):
        return "audio/flac"

    # OGG: OggS
    if header.startswith(b"OggS"):
        return "audio/ogg"

    # MP3: ID3 or MPEG frame sync (FF FB, FF F3, FF F2)
    if header.startswith(b"ID3"):
        return "audio/mp3"
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return "audio/mp3"

    # MP4 / MOV / M4A: ....ftyp
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"M4A ", b"M4B ", b"m4a "):
            return "audio/mp4"
        return "video/mp4"

    # AVI: RIFF....AVI 
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"AVI ":
        return "video/avi"

    # MKV / WebM: 1A 45 DF A3
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/mkv"

    return None


def validate_upload(
    header_bytes: bytes,
    file_size: int,
    module_id: str,
    max_bytes: int
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates uploaded file against size and magic bytes expected by the target module.
    Returns: (is_valid: bool, detected_mime: Optional[str], error_message: Optional[str])
    """
    if file_size <= 0:
        return False, None, "Uploaded file is empty (0 bytes)."

    if file_size > max_bytes:
        mb_limit = max_bytes // (1024 * 1024)
        return False, None, f"File exceeds maximum allowed upload size of {mb_limit} MB."

    detected_mime = detect_file_type(header_bytes)

    if module_id == "ai_aud":
        expected_category = "audio"
        valid_mimes = ["audio/wav", "audio/mp3", "audio/flac", "audio/ogg", "audio/mp4"]
        if detected_mime not in valid_mimes:
            return False, detected_mime, (
                f"File signature not recognized as supported audio (expected WAV, MP3, FLAC, OGG, or M4A). "
                f"Detected signature: {detected_mime or 'unknown raw binary'}."
            )

    elif module_id in ("ai_img", "image_forgery"):
        expected_category = "image"
        valid_mimes = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"]
        if detected_mime not in valid_mimes:
            return False, detected_mime, (
                f"File signature not recognized as supported image (expected JPEG, PNG, WEBP, BMP, or TIFF). "
                f"Detected signature: {detected_mime or 'unknown raw binary'}."
            )

    elif module_id == "ai_cctv":
        expected_category = "video"
        valid_mimes = ["video/mp4", "video/avi", "video/mkv"]
        if detected_mime not in valid_mimes:
            return False, detected_mime, (
                f"File signature not recognized as supported video (expected MP4, AVI, or MKV). "
                f"Detected signature: {detected_mime or 'unknown raw binary'}."
            )

    return True, detected_mime, None
