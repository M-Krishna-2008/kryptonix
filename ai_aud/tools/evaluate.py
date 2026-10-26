from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from audio_forensics.analyzer import analyze


def evaluate_folder(folder: Path, expected_verdict: str) -> dict:
    audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in audio_extensions]

    if not files:
        return {"count": 0}

    verdicts = {}
    logits = []

    for f in files:
        res = analyze(str(f))
        v = res.get("verdict", "inconclusive")
        verdicts[v] = verdicts.get(v, 0) + 1
        med = res.get("raw_metrics", {}).get("clip_summary", {}).get("median_logit")
        if med is not None:
            logits.append(med)

    correct = verdicts.get(expected_verdict, 0)
    acc = (correct / float(len(files))) * 100.0 if files else 0.0

    return {
        "count": len(files),
        "accuracy_pct": round(acc, 2),
        "verdict_breakdown": verdicts,
        "mean_logit": round(float(np.mean(logits)), 3) if logits else None,
        "median_logit": round(float(np.median(logits)), 3) if logits else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate audio forensics across dataset folders & attack types.")
    parser.add_argument("eval_dir", type=str, help="Directory containing subfolders of audio samples.")
    parser.add_argument("--expected", choices=["authentic", "likely_tampered"], default="likely_tampered", help="Expected verdict for the samples.")
    args = parser.parse_args()

    eval_path = Path(args.eval_dir)
    if not eval_path.exists():
        print(f"Directory not found: {eval_path}")
        sys.exit(1)

    print("=" * 65)
    print(f"Evaluating {eval_path.name} (Expected: {args.expected})")
    print("=" * 65)

    subdirs = [d for d in eval_path.iterdir() if d.is_dir()]
    if not subdirs:
        subdirs = [eval_path]

    for sd in subdirs:
        stats = evaluate_folder(sd, args.expected)
        print(f"\nFolder: {sd.name} ({stats['count']} files)")
        if stats["count"] == 0:
            print("  No audio files found.")
            continue
        print(f"  Match Rate:   {stats['accuracy_pct']}%")
        print(f"  Median Logit: {stats['median_logit']}")
        print(f"  Verdicts:     {stats['verdict_breakdown']}")


if __name__ == "__main__":
    main()
