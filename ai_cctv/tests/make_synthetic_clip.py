"""Synthetic CCTV video clip generator for automated testing and smoke verification.

Generates tiny, deterministic video clips using OpenCV without requiring external footage.
Clearly marked: FOR SMOKE TESTING ONLY - NOT REAL CCTV EVIDENCE.
"""

import argparse
from pathlib import Path
import cv2
import numpy as np


def create_synthetic_clip(
    output_path: str | Path,
    num_frames: int = 75,
    width: int = 640,
    height: int = 480,
    fps: float = 25.0,
    pattern: str = "cctv",
) -> Path:
    """Create a synthetic MP4 video clip."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_p), fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        if pattern == "cctv":
            # Dark room with noise and moving timestamp
            noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
            frame = cv2.add(frame, noise)
            # Add grid / walls
            cv2.rectangle(frame, (50, 50), (width - 50, height - 50), (80, 80, 80), 2)
            cv2.line(frame, (width // 2, 50), (width // 2, height - 50), (60, 60, 60), 1)
            # Moving element
            pos_x = (i * 8) % (width - 100) + 50
            cv2.circle(frame, (pos_x, height // 2), 25, (160, 160, 160), -1)
            # Timestamp OSD
            ts_text = f"CAM 01  2026-10-24 12:00:{i//25:02d}.{int((i%25)*40):03d}"
            cv2.putText(frame, ts_text, (20, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

        elif pattern == "blur":
            # Completely blurry frame (fails quality gate)
            frame[:] = 100

        elif pattern == "ai_simulated":
            # Warping geometric pattern simulating AI generative artifacts
            x = np.linspace(0, 4 * np.pi, width)
            y = np.linspace(0, 4 * np.pi, height)
            xx, yy = np.meshgrid(x, y)
            grid = (np.sin(xx + i * 0.2) * np.cos(yy + i * 0.2) * 127 + 128).astype(np.uint8)
            frame[:, :, 0] = grid
            frame[:, :, 1] = np.roll(grid, 20, axis=0)
            frame[:, :, 2] = np.roll(grid, 40, axis=1)

        writer.write(frame)

    writer.release()
    return out_p


def main():
    parser = argparse.ArgumentParser(description="Create synthetic test clip.")
    parser.add_argument("output", type=Path, help="Output file path (.mp4)")
    parser.add_argument("--frames", type=int, default=75, help="Number of frames to generate")
    parser.add_argument("--pattern", choices=["cctv", "blur", "ai_simulated"], default="cctv")
    args = parser.parse_args()

    clip_path = create_synthetic_clip(args.output, num_frames=args.frames, pattern=args.pattern)
    print(f"[Synthetic Generator] Created test clip at: {clip_path}")


if __name__ == "__main__":
    main()
