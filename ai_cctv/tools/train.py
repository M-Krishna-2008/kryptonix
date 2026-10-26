"""Fine-tuning script for YOLO11 CCTV classification.

Uses YOLO11-cls with imgsz=448 and mild augmentation.
Evaluates accuracy, ROC-AUC, and False Positive Rate (FPR) on held-out validation data.
Saves best model weights to models/best.pt.
"""

import argparse
import shutil
from pathlib import Path
import numpy as np
import torch
from ultralytics import YOLO
from sklearn.metrics import roc_auc_score, confusion_matrix


def main():
    parser = argparse.ArgumentParser(description="Fine-tune YOLO11-cls for AI CCTV detection.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Path to classification dataset folder")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--output-weights", type=Path, default=Path("ai_cctv_detection/models/best.pt"), help="Destination path for best weights")
    parser.add_argument("--workers", type=int, default=0, help="Number of worker threads (default 0 on Windows)")
    args = parser.parse_args()

    if not args.data_dir.exists() or not (args.data_dir / "train").exists():
        print(f"[Training Error] Training data directory not found: '{args.data_dir}'")
        print("Training data is archived. Run restore_training_data.bat <archive folder>")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    base_model_name = "yolo11s-cls.pt" if device == "cuda" else "yolo11n-cls.pt"

    # Check local models dir first
    local_base = Path("models") / base_model_name
    model_to_load = str(local_base) if local_base.is_file() else base_model_name

    print(f"[Training] Using device: {device} | Base model: {model_to_load}")
    model = YOLO(model_to_load)

    # Train with strictly mild augmentation (no heavy distortions, preserve forensic artifacts)
    results = model.train(
        data=str(args.data_dir.resolve()),
        epochs=args.epochs,
        imgsz=448,
        batch=args.batch,
        workers=args.workers,
        device=device,
        scale=0.0,       # No aggressive scale distortion
        degrees=0.0,     # No rotation
        fliplr=0.5,      # Mild horizontal flip
        hsv_h=0.015,     # Very subtle hue variation
        hsv_s=0.05,
        hsv_v=0.05,
        project="runs_train",
        name="ai_cctv_yolo11",
        exist_ok=True,
    )

    best_pt = Path(results.save_dir) / "weights" / "best.pt"
    if not best_pt.is_file():
        # Fallback to last.pt if best.pt not generated
        best_pt = Path(results.save_dir) / "weights" / "last.pt"

    if best_pt.is_file():
        args.output_weights.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(best_pt, args.output_weights)
        # Also copy to root models/best.pt if different
        alt_weights = Path("models/best.pt")
        if alt_weights.resolve() != args.output_weights.resolve():
            alt_weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(best_pt, alt_weights)
        print(f"[Training] Saved best checkpoint to: {args.output_weights}")

        # Run validation metrics evaluation
        val_dir = args.data_dir / "val"
        if val_dir.is_dir():
            print("[Training] Evaluating Validation Accuracy, ROC-AUC, and FPR...")
            val_model = YOLO(str(args.output_weights))
            val_results = val_model.val(data=str(args.data_dir.resolve()), imgsz=448, device=device)

            # Collect manual metrics
            y_true = []
            y_scores = []

            for cls_folder, label_val in [("real", 0), ("ai_generated", 1)]:
                folder_path = val_dir / cls_folder
                if folder_path.is_dir():
                    img_files = list(folder_path.glob("*.jpg")) + list(folder_path.glob("*.png"))
                    for img_p in img_files:
                        pred = val_model.predict(str(img_p), verbose=False, device=device)[0]
                        probs = pred.probs.data.cpu().numpy()
                        # Probability of ai_generated (index 1)
                        p_ai = float(probs[1]) if len(probs) > 1 else float(probs[0])
                        y_true.append(label_val)
                        y_scores.append(p_ai)

            if len(set(y_true)) > 1:
                auc = roc_auc_score(y_true, y_scores)
                preds = [1 if s >= 0.5 else 0 for s in y_scores]
                tn, fp, fn, tp = confusion_matrix(y_true, preds).ravel()
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                acc = (tp + tn) / len(y_true)

                print("\n" + "=" * 45)
                print(f" Validation Accuracy : {acc * 100:.2f}%")
                print(f" Validation ROC-AUC  : {auc:.4f}")
                print(f" False Positive Rate : {fpr * 100:.2f}% (Real CCTV falsely flagged)")
                print("=" * 45 + "\n")
            else:
                print(f"[Training] Top-1 Accuracy: {val_results.top1:.4f}")


if __name__ == "__main__":
    main()
