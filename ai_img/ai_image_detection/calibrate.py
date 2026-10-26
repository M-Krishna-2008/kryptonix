"""
Platt scaling calibration script for ai_image_detection.
Fits calibration parameters (a, b) on a dataset of known real and fake images:
    P(fake | logit) = 1 / (1 + exp(-(a * logit + b)))
and saves the result to configs/calibration.yaml.

Usage:
    python calibrate.py <real_dir> <fake_dir> [--out configs/calibration.yaml]
"""

import sys
import argparse
import datetime
import math
from pathlib import Path
from typing import List, Tuple
import yaml
import numpy as np

# Add parent directory if run directly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from analyzer import compute_raw_score_for_file


def fit_platt_scaling(logits: np.ndarray, labels: np.ndarray) -> Tuple[float, float]:
    """
    Fits parameters a, b for Platt scaling using negative log-likelihood minimization.
    Logistic formulation: P(y=1 | z) = 1 / (1 + exp(-(a * z + b)))
    """
    from scipy.optimize import minimize

    # Clip logits to prevent overflow
    z = np.clip(logits, -20.0, 20.0)
    y = labels.astype(float)

    # Initial guess: a=1.0, b=0.0
    def nll(params):
        a, b = params
        p = 1.0 / (1.0 + np.exp(-(a * z + b)))
        p = np.clip(p, 1e-12, 1.0 - 1e-12)
        loss = -np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
        return loss

    res = minimize(nll, [1.0, 0.0], method="L-BFGS-B")
    if res.success:
        return float(res.x[0]), float(res.x[1])
    return 1.0, 0.0


def collect_scores(folder: Path, label: int) -> Tuple[List[float], List[int]]:
    """Runs raw score extraction on all images in a folder."""
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    scores = []
    labels = []

    files = [f for f in folder.iterdir() if f.suffix.lower() in valid_exts and f.is_file()]
    print(f"[*] Processing {len(files)} images from {folder} (label={label})...")

    for f in files:
        try:
            score, err = compute_raw_score_for_file(str(f))
            if err:
                print(f"  [!] Skipped {f.name}: {err}")
                continue
            scores.append(score)
            labels.append(label)
        except Exception as e:
            print(f"  [!] Error processing {f.name}: {e}")

    return scores, labels


def main():
    parser = argparse.ArgumentParser(description="Calibrate UnivFD raw scores using Platt scaling.")
    parser.add_argument("real_dir", type=str, help="Directory containing known real images (camera-captured)")
    parser.add_argument("fake_dir", type=str, help="Directory containing known fake images (AI-generated)")
    parser.add_argument(
        "--out",
        type=str,
        default=str(CURRENT_DIR / "configs" / "calibration.yaml"),
        help="Path to output calibration.yaml"
    )

    args = parser.parse_args()

    real_path = Path(args.real_dir)
    fake_path = Path(args.fake_dir)

    if not real_path.is_dir():
        print(f"[-] Error: Real directory does not exist: {real_path}")
        sys.exit(1)
    if not fake_path.is_dir():
        print(f"[-] Error: Fake directory does not exist: {fake_path}")
        sys.exit(1)

    real_scores, real_labels = collect_scores(real_path, label=0)
    fake_scores, fake_labels = collect_scores(fake_path, label=1)

    all_scores = np.array(real_scores + fake_scores)
    all_labels = np.array(real_labels + fake_labels)

    if len(all_scores) < 4:
        print("[-] Insufficient sample count for calibration. Need at least 2 real and 2 fake images.")
        sys.exit(1)

    # Convert probability scores into logits
    eps = 1e-6
    clamped_scores = np.clip(all_scores, eps, 1.0 - eps)
    logits = np.log(clamped_scores / (1.0 - clamped_scores))

    print(f"[*] Fitting Platt scaling on {len(all_scores)} samples ({len(real_scores)} real, {len(fake_scores)} fake)...")
    a, b = fit_platt_scaling(logits, all_labels)

    print(f"[+] Fitted parameters: a = {a:.4f}, b = {b:.4f}")

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    calib_data = {
        "version": "1.0",
        "calibration": {
            "method": "platt_scaling",
            "a": round(a, 6),
            "b": round(b, 6),
            "fitted_samples": {
                "real": len(real_scores),
                "fake": len(fake_scores),
                "total": len(all_scores)
            },
            "fitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    }

    with open(out_file, "w", encoding="utf-8") as f:
        yaml.dump(calib_data, f, sort_keys=False)

    print(f"[+] Calibration configuration successfully written to {out_file}")


if __name__ == "__main__":
    main()
