"""
Verification of offline behavior and real model weights evaluation.
Sets HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 and evaluates sample images.
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import sys
from pathlib import Path

# Add project root
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ai_image_detection.analyzer import analyze

def main():
    print("=" * 80)
    print("OFFLINE VERIFICATION WITH REAL WEIGHTS (CLIP ViT-L/14 + UnivFD Linear Probe)")
    print("Environment flags: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1")
    print("=" * 80)

    # 1. Real Image
    real_sample = CURRENT_DIR / "ai_image_detection" / "tests" / "samples" / "sample_camera_authentic.jpg"
    res_real = analyze(str(real_sample), options={"no_cache": True})
    
    print("\n[+] EVALUATION: REAL PHOTO (sample_camera_authentic.jpg)")
    print(f"  Verdict:                {res_real['verdict']}")
    print(f"  Overall Confidence:     {res_real['overall_confidence']:.2%}")
    print(f"  Calibrated Fake Prob:   {res_real['raw_metrics'].get('calibrated_probability', 'N/A')}")
    print(f"  Raw Score:              {res_real['raw_metrics'].get('raw_score', 'N/A')}")
    print(f"  Per-crop Scores (3x3):  {res_real['raw_metrics'].get('per_crop_scores', [])}")
    print(f"  Photo Type:             {res_real['raw_metrics'].get('photo_type')}")
    print(f"  Errors:                 {res_real['errors']}")

    # 2. AI Generated Image
    ai_sample = CURRENT_DIR / "ai_image_detection" / "tests" / "samples" / "sample_ai_tampered.png"
    res_ai = analyze(str(ai_sample), options={"no_cache": True})

    print("\n[+] EVALUATION: AI-GENERATED IMAGE (sample_ai_tampered.png)")
    print(f"  Verdict:                {res_ai['verdict']}")
    print(f"  Overall Confidence:     {res_ai['overall_confidence']:.2%}")
    print(f"  Calibrated Fake Prob:   {res_ai['raw_metrics'].get('calibrated_probability', 'N/A')}")
    print(f"  Raw Score:              {res_ai['raw_metrics'].get('raw_score', 'N/A')}")
    print(f"  Per-crop Scores (3x3):  {res_ai['raw_metrics'].get('per_crop_scores', [])}")
    print(f"  Photo Type:             {res_ai['raw_metrics'].get('photo_type')}")
    print(f"  Errors:                 {res_ai['errors']}")
    print(f"  Findings Count:         {len(res_ai['findings'])}")
    for f in res_ai['findings']:
        print(f"    - [{f['severity'].upper()}] {f['check']}: {f['description']}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
