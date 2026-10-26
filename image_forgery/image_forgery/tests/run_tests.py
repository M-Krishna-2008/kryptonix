"""
Automated test suite for image_forgery module (TruFor + Classical Forensics).
Validates:
- All sample files against schemas.py (Pydantic model validation)
- SHA-256 integrity check against hashlib
- analyze() never raises under any circumstance
- Strict adherence to verdict and severity vocabularies
- Corrupt, tiny, and non-image files return 'inconclusive' with errors recorded
- Spliced sample triggers metadata and editing checks
- Format mismatch sample triggers format alert
- Deep engine tests print SKIPPED with clear reason if weights absent without failing suite
"""

import hashlib
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
PARENT_DIR = MODULE_ROOT.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from image_forgery.analyzer import analyze, get_available_engines_info
from image_forgery.schemas import AnalysisResult, SeverityEnum, VerdictEnum


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_engine_availability():
    print("\n--- Checking Engine Status ---")
    info = get_available_engines_info()
    for eng, data in info.items():
        avail = data.get("available")
        reason = data.get("reason")
        status_str = "AVAILABLE" if avail else "SKIPPED"
        print(f"[{status_str}] {eng}: {reason}")
    print("------------------------------\n")


def run_all_tests():
    samples_dir = MODULE_ROOT / "tests" / "samples"
    if not samples_dir.exists():
        print(f"ERROR: Samples directory not found: {samples_dir}")
        sys.exit(1)

    test_engine_availability()

    samples = [
        "authentic.jpg",
        "spliced.jpg",
        "copymove.jpg",
        "renamed.png",
        "tiny.jpg",
        "corrupt.jpg",
        "notimage.jpg"
    ]

    allowed_verdicts = {v.value for v in VerdictEnum}
    allowed_severities = {s.value for s in SeverityEnum}

    passed_count = 0
    total_count = len(samples)

    for sample_name in samples:
        sample_path = samples_dir / sample_name
        print(f"Testing sample: {sample_name}...")

        if not sample_path.exists():
            print(f"  FAIL: Sample file does not exist: {sample_path}")
            continue

        expected_sha = compute_file_sha256(sample_path)

        try:
            res = analyze(str(sample_path), {"max_side": 512, "use_cuda": False})
        except Exception as e:
            print(f"  FAIL: analyze() raised an exception: {e}")
            continue

        try:
            model = AnalysisResult(**res)
        except Exception as e:
            print(f"  FAIL: Result failed Pydantic schema validation: {e}")
            continue

        if res["evidence_file"]["sha256"] != expected_sha:
            print(f"  FAIL: SHA-256 mismatch")
            continue

        verdict = res["verdict"]
        if verdict not in allowed_verdicts:
            print(f"  FAIL: Invalid verdict value: {verdict}")
            continue

        invalid_sev = False
        for f in res.get("findings", []):
            if f["severity"] not in allowed_severities:
                print(f"  FAIL: Invalid finding severity: {f['severity']}")
                invalid_sev = True
                break
        if invalid_sev:
            continue

        if sample_name in ("corrupt.jpg", "notimage.jpg", "tiny.jpg"):
            if verdict != "inconclusive":
                print(f"  FAIL: {sample_name} expected verdict 'inconclusive', got '{verdict}'")
                continue
            if len(res.get("errors", [])) == 0:
                print(f"  FAIL: {sample_name} expected error recorded in 'errors' field")
                continue

        if sample_name == "renamed.png":
            found_mismatch = any(f["check"] == "FORMAT_MISMATCH" for f in res.get("findings", []))
            if not found_mismatch:
                print(f"  FAIL: renamed.png expected FORMAT_MISMATCH finding")
                continue

        if sample_name == "spliced.jpg":
            found_meta = any(f["check"] == "METADATA_SOFTWARE" for f in res.get("findings", []))
            if not found_meta:
                print(f"  FAIL: spliced.jpg expected METADATA_SOFTWARE finding")
                continue

        print(f"  PASS: {sample_name} -> Verdict: {verdict}, Confidence: {res['overall_confidence']}, Findings: {len(res['findings'])}, Errors: {len(res['errors'])}")
        passed_count += 1

    print(f"\n==========================================")
    print(f"Tests Completed: {passed_count}/{total_count} PASSED")
    print(f"==========================================")

    if passed_count != total_count:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
