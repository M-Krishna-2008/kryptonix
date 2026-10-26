"""
Decision logic and threshold evaluation for ai_image_detection.
Maps calibrated fake probabilities and photo types to PS-05 verdicts and findings.
"""

from typing import Dict, Any, Tuple
from pathlib import Path
import yaml


def load_thresholds(config_path: Path | None = None) -> Dict[str, Any]:
    """Load decision thresholds from YAML config file."""
    if config_path is None:
        config_path = Path(__file__).parent / "configs" / "thresholds.yaml"
    
    if not config_path.is_file():
        # Fallback defaults if file is missing
        return {
            "camera_photo": {"fake": 0.80, "real": 0.20},
            "ai_render": {"fake": 0.75, "real": 0.25},
            "social_media_reupload": {"fake": 0.90, "real": 0.10},
            "screenshot": {"fake": 0.95, "real": 0.05},
            "edited": {"fake": 0.90, "real": 0.10},
            "small_or_blurry": {"fake": None, "real": None},
        }
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("thresholds", {})


def evaluate_decision(
    photo_type: str,
    calibrated_prob: float,
    thresholds: Dict[str, Any] | None = None
) -> Tuple[str, str, float, str, Dict[str, Any]]:
    """
    Evaluates calibrated fake probability against photo-type specific thresholds.

    Returns:
        (verdict, decision_label, overall_confidence, explanation, threshold_info)
        verdict: 'authentic' | 'suspicious' | 'likely_tampered' | 'inconclusive'
        decision_label: 'Real' | 'Likely fake' | 'Uncertain' | 'Insufficient quality'
    """
    if thresholds is None:
        thresholds = load_thresholds()

    type_cfg = thresholds.get(photo_type, thresholds.get("camera_photo", {"fake": 0.80, "real": 0.20}))
    fake_th = type_cfg.get("fake")
    real_th = type_cfg.get("real")

    threshold_info = {
        "photo_type": photo_type,
        "fake_threshold": fake_th,
        "real_threshold": real_th,
        "calibrated_prob": round(float(calibrated_prob), 4)
    }

    # Branch 1: Insufficient quality (small or blurry)
    if photo_type == "small_or_blurry" or fake_th is None or real_th is None:
        verdict = "inconclusive"
        decision_label = "Insufficient quality"
        overall_confidence = 0.50
        explanation = (
            "Image quality is insufficient (dimensions too small or excessive blurriness) "
            "for the neural network to reliably distinguish AI synthesis artifacts from natural textures."
        )
        return verdict, decision_label, overall_confidence, explanation, threshold_info

    # Branch 2: Likely Fake (exceeds fake threshold)
    if calibrated_prob >= fake_th:
        verdict = "likely_tampered"
        decision_label = "Likely fake"
        # Overall confidence reflects how strongly it exceeds the threshold
        overall_confidence = min(0.99, max(0.60, calibrated_prob))
        explanation = (
            f"The image exhibits synthetic frequency and semantic artifacts characteristic of AI generation "
            f"(calibrated fake probability {calibrated_prob * 100:.1f}%, exceeding the {fake_th * 100:.0f}% "
            f"threshold for {photo_type.replace('_', ' ')})."
        )
        return verdict, decision_label, round(overall_confidence, 4), explanation, threshold_info

    # Branch 3: Authentic (falls at or below real threshold)
    if calibrated_prob <= real_th:
        verdict = "authentic"
        decision_label = "Real"
        # Confidence reflects how low the fake probability is
        overall_confidence = min(0.99, max(0.60, 1.0 - calibrated_prob))
        explanation = (
            f"The image characteristics are consistent with genuine camera sensor capture "
            f"(calibrated fake probability {calibrated_prob * 100:.1f}%, within the {real_th * 100:.0f}% "
            f"authentic boundary for {photo_type.replace('_', ' ')})."
        )
        return verdict, decision_label, round(overall_confidence, 4), explanation, threshold_info

    # Branch 4: Uncertain band (between real_th and fake_th)
    midpoint = (fake_th + real_th) / 2.0
    threshold_info["midpoint"] = round(midpoint, 4)

    if calibrated_prob > midpoint:
        verdict = "suspicious"
        decision_label = "Uncertain"
        overall_confidence = round(calibrated_prob, 4)
        explanation = (
            f"The image falls in the upper uncertain zone (probability {calibrated_prob * 100:.1f}% "
            f"between {midpoint * 100:.0f}% and {fake_th * 100:.0f}% for {photo_type.replace('_', ' ')}). "
            f"AI generation or heavy manipulation is suspected but cannot be conclusively confirmed."
        )
    else:
        verdict = "inconclusive"
        decision_label = "Uncertain"
        overall_confidence = round(1.0 - calibrated_prob, 4)
        explanation = (
            f"The AI-detection score ({calibrated_prob * 100:.1f}%) lies in the neutral uncertain band "
            f"between {real_th * 100:.0f}% and {midpoint * 100:.0f}% for {photo_type.replace('_', ' ')}. "
            f"The features are ambiguous; further forensic analysis is required."
        )

    return verdict, decision_label, overall_confidence, explanation, threshold_info
