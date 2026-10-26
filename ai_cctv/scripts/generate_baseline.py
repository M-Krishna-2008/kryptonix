import os
import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path

baseline_dir = Path("baseline")
baseline_dir.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_cctv_detection.analyzer import analyze

samples = [
    Path("tests/sample_1_cctv.mp4"),
    Path("tests/sample_2_blurry.mp4"),
    Path("tests/sample_3_tampered.mp4"),
]

print("=== RUNNING BASELINE INFERENCE ON 3 SAMPLES ===")

for s in samples:
    print(f"\nRunning analyze() on {s.name}...")
    t0 = time.perf_counter()
    res = analyze(str(s))
    elapsed = time.perf_counter() - t0

    out_file = baseline_dir / f"{s.stem}_result.json"
    res_to_save = dict(res)
    res_to_save["_benchmark_elapsed_sec"] = elapsed
    out_file.write_text(json.dumps(res_to_save, indent=2), encoding="utf-8")

    print(f"  Elapsed:    {elapsed:.3f}s")
    print(f"  Verdict:    {res.get('verdict')}")
    print(f"  Confidence: {res.get('overall_confidence')}")
    print(f"  Saved to:   {out_file}")

# Record model hashes
hashes_file = baseline_dir / "hashes.txt"
with open(hashes_file, "w", encoding="utf-8") as hf:
    for m in [Path("ai_cctv_detection/models/best.pt"), Path("models/best.pt"), Path("models/yolo11s-cls.pt")]:
        if m.exists():
            h = hashlib.sha256(m.read_bytes()).hexdigest()
            line = f"{h}  {m}\n"
            hf.write(line)
            print("Recorded hash:", line.strip())

# Run pytest suite and save output
print("\nRunning pytest suite...")
pytest_proc = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_analyzer.py", "-v"],
    capture_output=True,
    text=True
)
pytest_log = baseline_dir / "pytest_baseline.txt"
pytest_log.write_text(pytest_proc.stdout + "\n" + pytest_proc.stderr, encoding="utf-8")
print(f"Pytest finished with return code {pytest_proc.returncode}. Log saved to {pytest_log}")
print(pytest_proc.stdout)
