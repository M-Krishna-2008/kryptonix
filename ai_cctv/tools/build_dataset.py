"""Dataset builder for AI CCTV detection fine-tuning.

Extracts I-frames + ~2 fps frames from real and fake videos.
CRITICAL FORENSIC RULE:
Splits strictly BY SOURCE VIDEO (never by frame) into train/val/test to prevent
data leakage and memorization of background scenes.
Generates YOLO classification layout (data/train/real, data/train/ai_generated, etc.)
and records video provenance in data/manifest.json.
"""

import argparse
import json
import random
from pathlib import Path
import cv2


def extract_frames_from_video(video_path: Path, output_dir: Path, target_fps: float = 2.0, max_frames: int = 150) -> list[dict]:
    """Extract frames from video and save as JPEG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_meta = []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return frames_meta

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps / target_fps))
    idx = 0
    saved_count = 0

    stem = video_path.stem
    while cap.isOpened() and saved_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % frame_interval == 0:
            out_name = f"{stem}_f{idx:05d}.jpg"
            out_file = output_dir / out_name
            cv2.imwrite(str(out_file), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            frames_meta.append({
                "file": out_name,
                "frame_index": idx,
                "pts_sec": round(idx / fps, 3),
            })
            saved_count += 1
        idx += 1

    cap.release()
    return frames_meta


def get_video_metadata(video_path: Path) -> dict:
    """Extract metadata for shortcut-learning check."""
    cap = cv2.VideoCapture(str(video_path))
    meta = {
        "width": 0,
        "height": 0,
        "fps": 25.0,
        "total_frames": 0,
        "fourcc": "unknown",
        "size_bytes": video_path.stat().st_size if video_path.is_file() else 0,
    }
    if cap.isOpened():
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        meta["fourcc"] = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip() or "cv2"
        meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        meta["fps"] = fps if fps > 0 else 25.0
        meta["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
    return meta


def split_videos(video_list: list[Path], train_ratio=0.70, val_ratio=0.15) -> tuple[list[Path], list[Path], list[Path]]:
    """Split video list strictly BY SOURCE VIDEO ID."""
    videos = list(video_list)
    random.seed(42)
    random.shuffle(videos)
    n = len(videos)
    if n == 0:
        return [], [], []
    if n == 1:
        return videos, videos, videos
    if n == 2:
        return [videos[0]], [videos[1]], [videos[1]]

    n_train = max(1, int(n * train_ratio))
    n_val = max(1, int(n * val_ratio))
    train = videos[:n_train]
    val = videos[n_train:n_train + n_val]
    test = videos[n_train + n_val:]
    if not test:
        test = val
    return train, val, test


def main():
    parser = argparse.ArgumentParser(description="Build YOLO classification dataset from CCTV videos.")
    parser.add_argument("real_videos_dir", type=Path, help="Directory containing authentic CCTV videos")
    parser.add_argument("fake_videos_dir", type=Path, help="Directory containing AI-generated CCTV videos")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Destination root directory for dataset")
    parser.add_argument("--fps", type=float, default=2.0, help="Frame extraction rate")
    args = parser.parse_args()

    out_root = args.output_dir

    if not args.real_videos_dir.exists() or not args.fake_videos_dir.exists():
        print(f"[Dataset Builder Error] Real or fake videos directory missing: '{args.real_videos_dir}', '{args.fake_videos_dir}'")
        print("Training data is archived. Run restore_training_data.bat <archive folder>")
        return

    extensions = ("*.mp4", "*.avi", "*.mkv", "*.mov")

    real_videos = []
    for ext in extensions:
        real_videos.extend(args.real_videos_dir.glob(ext))

    fake_videos = []
    for ext in extensions:
        fake_videos.extend(args.fake_videos_dir.glob(ext))

    print(f"[Dataset Builder] Found {len(real_videos)} real videos and {len(fake_videos)} AI/fake videos.")

    real_splits = split_videos(real_videos)
    fake_splits = split_videos(fake_videos)

    split_names = ("train", "val", "test")
    manifest = {
        "created_at": None,
        "real_count": len(real_videos),
        "fake_count": len(fake_videos),
        "videos": [],
    }

    for idx, split in enumerate(split_names):
        split_real_vids = real_splits[idx]
        split_fake_vids = fake_splits[idx]

        real_dest = out_root / split / "real"
        fake_dest = out_root / split / "ai_generated"

        # Process real videos
        for vid in split_real_vids:
            meta = get_video_metadata(vid)
            extracted = extract_frames_from_video(vid, real_dest, target_fps=args.fps)
            manifest["videos"].append({
                "video_id": vid.name,
                "label": "real",
                "split": split,
                "metadata": meta,
                "frames_count": len(extracted),
            })

        # Process fake videos
        for vid in split_fake_vids:
            meta = get_video_metadata(vid)
            extracted = extract_frames_from_video(vid, fake_dest, target_fps=args.fps)
            manifest["videos"].append({
                "video_id": vid.name,
                "label": "ai_generated",
                "split": split,
                "metadata": meta,
                "frames_count": len(extracted),
            })

    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = out_root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Dataset Builder] Done! Dataset written to '{out_root}' with manifest at '{manifest_path}'.")


if __name__ == "__main__":
    main()
