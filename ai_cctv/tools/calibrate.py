"""Fit Platt scaling calibration on held-out validation set.

Fits logistic regression: logit(p_true) = a * logit(p_raw) + b
and writes updated parameters to configs/calibration.yaml.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import yaml
from sklearn.linear_model import LogisticRegression
import torch
from ultralytics import YOLO


def compute_logits(probs: np.ndarray) -> np.ndarray:
    """Transform probabilities to logits with clamping."""
    clamped = np.clip(probs, 1e-6, 1.0 - 1e-6)
    return np.log(clamped / (1.0 - clamped))


def main():
    parser = argparse.ArgumentParser(description="Fit Platt scaling calibration on validation split.")
    parser.add_argument("--model", type=Path, default=Path("ai_cctv_detection/models/best.pt"), help="Trained YOLO11-cls model")
    parser.add_argument("--val-dir", type=Path, default=Path("data/val"), help="Validation directory (with real/ and ai_generated/)")
    parser.add_argument("--output-config", type=Path, default=Path("ai_cctv_detection/configs/calibration.yaml"), help="Path to calibration.yaml")
    args = parser.parse_args()

    if not args.model.is_file():
        print(f"[Calibrate Error] Model not found: {args.model}")
        return

    if not args.val_dir.is_dir():
        print(f"[Calibrate Error] Validation directory not found: {args.val_dir}")
        print("Training data is archived. Run restore_training_data.bat <archive folder>")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = YOLO(str(args.model))

    # Dynamically resolve ai_generated class index
    ai_idx = 1
    for k, v in model.names.items():
        if any(term in str(v).lower() for term in ["ai", "fake", "synth", "tamp"]):
            ai_idx = k
            break

    y_true = []
    raw_probs = []

    for cls_folder, label in [("real", 0), ("ai_generated", 1)]:
        folder = args.val_dir / cls_folder
        if not folder.is_dir():
            continue
        images = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
        for img_p in images:
            pred = model.predict(str(img_p), verbose=False, device=device)[0]
            probs = pred.probs.data.cpu().numpy()
            p_ai = float(probs[ai_idx])
            y_true.append(label)
            raw_probs.append(p_ai)

    if len(set(y_true)) < 2:
        print("[Calibrate] Need both real and ai_generated validation samples to fit calibration.")
        return

    logits = compute_logits(np.array(raw_probs)).reshape(-1, 1)
    y_arr = np.array(y_true)

    clf = LogisticRegression()
    clf.fit(logits, y_arr)

    a = float(clf.coef_[0][0])
    b = float(clf.intercept_[0])

    print(f"[Calibrate] Fitted Platt Scaling: a = {a:.4f}, b = {b:.4f}")

    args.output_config.parent.mkdir(parents=True, exist_ok=True)
    calib_data = {
        "version": "1.0",
        "method": "platt",
        "a": round(a, 4),
        "b": round(b, 4),
        "last_calibrated_at": datetime.now(timezone.utc).isoformat(),
        "validation_samples": len(y_true),
    }

    with open(args.output_config, "w", encoding="utf-8") as f:
        yaml.dump(calib_data, f, sort_keys=False)

    print(f"[Calibrate] Updated configuration saved to: {args.output_config}")


if __name__ == "__main__":
    main()
