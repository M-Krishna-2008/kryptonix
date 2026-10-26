"""
Forensic Calibration & Threshold Tuning Script.
Runs all sample images in tests/calibration/authentic/ and tests/calibration/tampered/,
evaluates TruFor global integrity scores and computed verdicts, and prints a formatted
report allowing the user to tune classification thresholds.

Usage:
    python tests/calibration/run_calibration.py
    python tests/calibration/run_calibration.py --auth-thresh 0.35 --tamp-thresh 0.60
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analyzer import analyze
from engines.config import TRUFOR_AUTHENTIC_THRESHOLD, TRUFOR_TAMPERED_THRESHOLD


def parse_args():
    parser = argparse.ArgumentParser(description="Image Forgery Forensic Threshold Calibration")
    parser.add_argument(
        "--auth-thresh",
        type=float,
        default=TRUFOR_AUTHENTIC_THRESHOLD,
        help=f"TruFor authenticity threshold (default: {TRUFOR_AUTHENTIC_THRESHOLD})"
    )
    parser.add_argument(
        "--tamp-thresh",
        type=float,
        default=TRUFOR_TAMPERED_THRESHOLD,
        help=f"TruFor tampering threshold (default: {TRUFOR_TAMPERED_THRESHOLD})"
    )
    parser.add_argument(
        "--authentic-dir",
        type=str,
        default=str(PROJECT_ROOT / "tests" / "calibration" / "authentic"),
        help="Path to directory containing authentic sample images"
    )
    parser.add_argument(
        "--tampered-dir",
        type=str,
        default=str(PROJECT_ROOT / "tests" / "calibration" / "tampered"),
        help="Path to directory containing tampered/manipulated sample images"
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=1024,
        help="Max image dimension for inference (default: 1024)"
    )
    return parser.parse_args()


def get_image_files(directory: Path):
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
    if not directory.exists():
        return []
    return [p for p in sorted(directory.iterdir()) if p.is_file() and p.suffix.lower() in valid_exts]


def main():
    args = parse_args()

    # Override threshold environment variables for calibration run if specified
    os.environ["TRUFOR_AUTHENTIC_THRESHOLD"] = str(args.auth_thresh)
    os.environ["TRUFOR_TAMPERED_THRESHOLD"] = str(args.tamp_thresh)

    auth_dir = Path(args.authentic_dir)
    tamp_dir = Path(args.tampered_dir)

    auth_files = get_image_files(auth_dir)
    tamp_files = get_image_files(tamp_dir)

    total_images = len(auth_files) + len(tamp_files)
    if total_images == 0:
        print(f"No test images found in:\n  {auth_dir}\n  {tamp_dir}")
        print("Please place test images into tests/calibration/authentic/ and tests/calibration/tampered/")
        sys.exit(1)

    print("=" * 90)
    print("           PS-05 Image Forgery: Forensic Calibration & Threshold Tuning")
    print("=" * 90)
    print(f"  Authentic Threshold:   < {args.auth_thresh:.3f} -> Likely Authentic")
    print(f"  Inconclusive Range:     [{args.auth_thresh:.3f}, {args.tamp_thresh:.3f}] -> Inconclusive")
    print(f"  Tampered Threshold:     > {args.tamp_thresh:.3f} -> Likely Manipulated")
    print(f"  Authentic Samples:      {len(auth_files)} file(s) in {auth_dir.name}/")
    print(f"  Tampered Samples:       {len(tamp_files)} file(s) in {tamp_dir.name}/")
    print("=" * 90)
    print()

    # Table Header
    header_fmt = "{:<12} | {:<24} | {:<12} | {:<18} | {:<10} | {:<12}"
    print(header_fmt.format("Ground Truth", "Image File", "TruFor Score", "Verdict", "Confidence", "Status"))
    print("-" * 90)

    results = []
    correct_auth = 0
    correct_tamp = 0
    inconclusive_count = 0

    # 1. Evaluate Authentic Images
    for f in auth_files:
        opts = {"max_side": args.max_side, "use_cuda": False}
        t0 = time.time()
        res = analyze(str(f), opts)
        elapsed = time.time() - t0

        breakdown = res.get("confidence_breakdown") or (res.get("raw_metrics", {}).get("confidence_breakdown")) or {}
        trufor_score = breakdown.get("trufor_global_score")
        score_str = f"{trufor_score:.3f}" if trufor_score is not None else "N/A"
        verdict = res.get("verdict", "unknown")
        conf = res.get("overall_confidence", 0.0)

        # Status check
        if verdict == "authentic":
            status = "PASS (OK)"
            correct_auth += 1
        elif verdict == "inconclusive":
            status = "INCONCLUSIVE"
            inconclusive_count += 1
        else:
            status = "FALSE ALARM"

        print(header_fmt.format("AUTHENTIC", f.name[:24], score_str, verdict, f"{conf*100:.0f}%", status))
        results.append({"type": "AUTHENTIC", "file": f.name, "score": trufor_score, "verdict": verdict, "status": status})

    # 2. Evaluate Tampered Images
    for f in tamp_files:
        opts = {"max_side": args.max_side, "use_cuda": False}
        t0 = time.time()
        res = analyze(str(f), opts)
        elapsed = time.time() - t0

        breakdown = res.get("confidence_breakdown") or (res.get("raw_metrics", {}).get("confidence_breakdown")) or {}
        trufor_score = breakdown.get("trufor_global_score")
        score_str = f"{trufor_score:.3f}" if trufor_score is not None else "N/A"
        verdict = res.get("verdict", "unknown")
        conf = res.get("overall_confidence", 0.0)

        # Status check
        if verdict == "likely_tampered":
            status = "PASS (OK)"
            correct_tamp += 1
        elif verdict == "inconclusive":
            status = "INCONCLUSIVE"
            inconclusive_count += 1
        else:
            status = "MISSED (FN)"

        print(header_fmt.format("TAMPERED", f.name[:24], score_str, verdict, f"{conf*100:.0f}%", status))
        results.append({"type": "TAMPERED", "file": f.name, "score": trufor_score, "verdict": verdict, "status": status})

    print("-" * 90)
    print()
    print("=== SUMMARY METRICS ===")
    if len(auth_files) > 0:
        auth_acc = (correct_auth / len(auth_files)) * 100
        print(f"  Authentic Specificity (True Negative Rate):  {correct_auth}/{len(auth_files)} ({auth_acc:.1f}%)")
    if len(tamp_files) > 0:
        tamp_acc = (correct_tamp / len(tamp_files)) * 100
        print(f"  Tampered Sensitivity (True Positive Rate):    {correct_tamp}/{len(tamp_files)} ({tamp_acc:.1f}%)")
    print(f"  Inconclusive Rate:                           {inconclusive_count}/{total_images} ({(inconclusive_count/total_images)*100:.1f}%)")
    print()
    print("=== THRESHOLD TUNING TIP ===")
    print("  To adjust thresholds permanently, edit 'engines/config.py':")
    print(f"    TRUFOR_AUTHENTIC_THRESHOLD = {args.auth_thresh}")
    print(f"    TRUFOR_TAMPERED_THRESHOLD  = {args.tamp_thresh}")
    print("=" * 90)


if __name__ == "__main__":
    main()
