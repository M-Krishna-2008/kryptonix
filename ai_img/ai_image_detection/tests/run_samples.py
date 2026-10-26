"""
Forensic Sample Evaluation Runner
Executes analyzer.analyze() against all sample images in tests/samples/
and renders a structured ASCII forensic report table.
"""

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from analyzer import analyze

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"


def run_all_samples():
    print("=" * 110)
    print(" PS-05 DIGITAL EVIDENCE PLATFORM: AI IMAGE DETECTION (UnivFD) SAMPLE EVALUATION ")
    print("=" * 110)

    if not SAMPLES_DIR.is_dir():
        print(f"[-] Samples directory not found: {SAMPLES_DIR}")
        return

    sample_files = sorted([
        f for f in SAMPLES_DIR.iterdir()
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".bmp"}
    ])

    if not sample_files:
        print("[-] No sample images found. Run `python tests/generate_samples.py` first.")
        return

    # Header
    col_file = 28
    col_type = 22
    col_prob = 12
    col_verdict = 18
    col_conf = 12
    col_find = 10

    header = (
        f"{'Evidence File':<{col_file}} | "
        f"{'Photo Type':<{col_type}} | "
        f"{'Fake Prob':<{col_prob}} | "
        f"{'Verdict':<{col_verdict}} | "
        f"{'Confidence':<{col_conf}} | "
        f"{'Findings':<{col_find}}"
    )
    separator = "-" * len(header)

    print(header)
    print(separator)

    results = []
    for f in sample_files:
        res = analyze(str(f))
        results.append(res)

        name = f.name[:col_file-2]
        pt = str(res.get("raw_metrics", {}).get("photo_type", "unknown"))[:col_type-2]
        prob = res.get("raw_metrics", {}).get("calibrated_probability")
        prob_str = f"{prob * 100:.1f}%" if prob is not None else "N/A"
        verdict = res.get("verdict", "unknown")
        conf = res.get("overall_confidence", 0.0)
        conf_str = f"{conf * 100:.0f}%"
        findings_count = str(len(res.get("findings", [])))

        row = (
            f"{name:<{col_file}} | "
            f"{pt:<{col_type}} | "
            f"{prob_str:<{col_prob}} | "
            f"{verdict:<{col_verdict}} | "
            f"{conf_str:<{col_conf}} | "
            f"{findings_count:<{col_find}}"
        )
        print(row)

    print(separator)
    print(f"[+] Evaluated {len(results)} sample images successfully.")

    # Check for warnings or weight status
    has_errors = any(len(r.get("errors", [])) > 0 for r in results)
    if has_errors:
        print("\n[!] Execution Notes:")
        for r in results:
            if r.get("errors"):
                print(f"  - {r['evidence_file']['name']}: {'; '.join(r['errors'])}")
        print("  (Note: If weights are missing, see setup_model.md for offline download instructions.)")
    print("=" * 110)


if __name__ == "__main__":
    run_all_samples()
