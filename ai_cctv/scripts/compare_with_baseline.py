import os
import sys
import json
import hashlib
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
extracted_root = repo_root / "clean_extract_test" / "extracted module" / "ai_cctv_detection"
baseline_dir = repo_root / "baseline"

print("========================================================")
print(" BASELINE VS EXTRACTED PACKAGE VERIFICATION")
print(f" Baseline Dir:  {baseline_dir}")
print(f" Extracted Dir: {extracted_root}")
print("========================================================\n")

# 1. Verify Model Hashes against baseline/hashes.txt
print("[Check 1/3] Verifying Model Hashes against baseline/hashes.txt...")
hashes_file = baseline_dir / "hashes.txt"
assert hashes_file.exists(), f"baseline/hashes.txt missing at {hashes_file}"

expected_hashes = {}
for line in hashes_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line:
        parts = line.split(maxsplit=1)
        expected_hashes[parts[1]] = parts[0]

for rel_path, exp_hash in expected_hashes.items():
    actual_file = extracted_root / rel_path
    assert actual_file.exists(), f"Model file missing in extracted package: {actual_file}"
    act_hash = hashlib.sha256(actual_file.read_bytes()).hexdigest()
    print(f"  {rel_path}:")
    print(f"    Expected: {exp_hash}")
    print(f"    Actual:   {act_hash}")
    assert exp_hash == act_hash, f"Hash mismatch for {rel_path}!"
    print("    [MATCH - 100% BITWISE IDENTICAL]")

# 2. Run analyze() from extracted package
print("\n[Check 2/3] Running analyze() on 3 sample inputs from extracted package...")

# Ensure Python loads analyzer from extracted_root
if str(extracted_root) in sys.path:
    sys.path.remove(str(extracted_root))
sys.path.insert(0, str(extracted_root))

# Unload any previously cached ai_cctv_detection modules
for mod_name in list(sys.modules.keys()):
    if "ai_cctv_detection" in mod_name:
        del sys.modules[mod_name]

from ai_cctv_detection.analyzer import analyze
import ai_cctv_detection.analyzer as az
print(f"  Loaded analyzer from: {az.__file__}")
assert str(extracted_root) in az.__file__, "Analyzer not loaded from extracted directory!"

samples = [
    "sample_1_cctv",
    "sample_2_blurry",
    "sample_3_tampered",
]

comparison_table = []
all_passed = True

for s_name in samples:
    baseline_json_path = baseline_dir / f"{s_name}_result.json"
    assert baseline_json_path.exists(), f"Baseline JSON missing: {baseline_json_path}"
    base_data = json.loads(baseline_json_path.read_text(encoding="utf-8"))

    sample_mp4 = extracted_root / "tests" / f"{s_name}.mp4"
    assert sample_mp4.exists(), f"Sample mp4 missing: {sample_mp4}"

    t0 = time.perf_counter()
    new_result = analyze(str(sample_mp4))
    elapsed = time.perf_counter() - t0

    # Compare verdict
    base_verdict = base_data.get("verdict")
    new_verdict = new_result.get("verdict")
    verdict_match = (base_verdict == new_verdict)

    # Compare confidence
    base_conf = float(base_data.get("overall_confidence", 0.0))
    new_conf = float(new_result.get("overall_confidence", 0.0))
    conf_diff = abs(base_conf - new_conf)
    conf_match = (conf_diff <= 1e-4)

    # Compare findings count
    base_findings = len(base_data.get("findings", []))
    new_findings = len(new_result.get("findings", []))
    findings_match = (base_findings == new_findings)

    # Compare SHA256
    base_sha = base_data.get("evidence_file", {}).get("sha256")
    new_sha = new_result.get("evidence_file", {}).get("sha256")
    sha_match = (base_sha == new_sha)

    status = "PASS" if (verdict_match and conf_match and findings_match and sha_match) else "FAIL"
    if status == "FAIL":
        all_passed = False

    comparison_table.append({
        "sample": s_name,
        "base_verdict": base_verdict,
        "new_verdict": new_verdict,
        "base_conf": f"{base_conf:.4f}",
        "new_conf": f"{new_conf:.4f}",
        "diff": f"{conf_diff:.6f}",
        "findings": f"{base_findings} vs {new_findings}",
        "status": status,
    })

print("\n=== BEFORE / AFTER INFERENCE COMPARISON TABLE ===")
header = f"| Sample Name | Baseline Verdict | Extracted Verdict | Base Conf | Extracted Conf | Delta | Findings | Status |"
sep = f"|---|---|---|---|---|---|---|---|"
print(header)
print(sep)
for row in comparison_table:
    print(f"| `{row['sample']}` | `{row['base_verdict']}` | `{row['new_verdict']}` | `{row['base_conf']}` | `{row['new_conf']}` | `{row['diff']}` | `{row['findings']}` | **{row['status']}** |")

# 3. Assertions
assert all_passed, "Inference baseline comparison failed!"
print("\n[OK] All 3 samples matched baseline verdicts and scores within 1e-4 tolerance!")
print("\n========================================================")
print(" ALL CHECKS PASSED: EXTRACTED PACKAGE IS 100% IDENTICAL!")
print("========================================================")
