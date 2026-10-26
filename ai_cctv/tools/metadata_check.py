"""Shortcut-learning check on CCTV video metadata.

Trains a lightweight decision tree classifier exclusively on video metadata
(resolution, bitrate, fps, container/codec) recorded in manifest.json.
WARNS prominently if real vs fake can be predicted with high accuracy from metadata
alone, which indicates the dataset suffers from shortcut learning / distribution shift.
"""

import argparse
import json
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import cross_val_score


def main():
    parser = argparse.ArgumentParser(description="Check for metadata shortcut learning in video dataset.")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.json"), help="Dataset manifest file")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"[Metadata Check] Manifest file not found: {args.manifest}")
        print("Training data is archived. Run restore_training_data.bat <archive folder>")
        return

    with open(args.manifest, "r", encoding="utf-8") as f:
        data = json.load(f)

    videos = data.get("videos", [])
    if len(videos) < 4:
        print("[Metadata Check] Not enough videos in manifest to run meaningful shortcut test.")
        return

    features = []
    labels = []

    for item in videos:
        meta = item.get("metadata", {})
        w = float(meta.get("width", 0))
        h = float(meta.get("height", 0))
        fps = float(meta.get("fps", 0))
        bitrate = float(meta.get("bitrate", 0))
        size = float(meta.get("size_bytes", 0))

        features.append([w, h, fps, bitrate, size])
        labels.append(1 if item.get("label") == "ai_generated" else 0)

    X = np.array(features)
    y = np.array(labels)

    if len(set(y)) < 2:
        print("[Metadata Check] Manifest only contains one class; cannot perform check.")
        return

    clf = DecisionTreeClassifier(max_depth=3, random_state=42)
    scores = cross_val_score(clf, X, y, cv=min(3, len(y)))
    mean_acc = float(np.mean(scores))

    print("\n" + "=" * 55)
    print(f" Metadata-Only Classification Accuracy: {mean_acc * 100:.1f}%")
    print("=" * 55)

    if mean_acc >= 0.85:
        print("[CRITICAL WARNING] SHORTCUT LEARNING DETECTED!")
        print("Real vs Fake can be classified with high accuracy from resolution,")
        print("fps, or bitrate alone without inspecting pixel textures!")
        print("ACTION REQUIRED:")
        print("- Match real and AI videos to identical resolutions (e.g. 1920x1080 or 1280x720).")
        print("- Re-encode AI clips with the same codec (H.264/H.265) and bitrate as your CCTV cameras.")
        print("=" * 55 + "\n")
    else:
        print("[SUCCESS] Metadata distributions appear balanced.")
        print("Classifier cannot rely on simple container shortcuts.")
        print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
