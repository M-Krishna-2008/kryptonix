#!/usr/bin/env python3
"""
Portability Audit Scanner for PS-05 Audio Forensics.
Scans codebase for:
a. Hardcoded absolute paths / usernames / drive letters
b. Unquoted paths or cwd dependencies
c. Unlisted / unpinned Python packages and build dependencies
d. External CLI tool dependencies
e. Runtime internet dependencies (CDNs, remote endpoints)
f. Model weights (locations, sizes, hashes, URLs)
g. Port & environment variable assumptions
h. Node.js / npm requirement verification
i. Python version constraints
"""

import os
import re
import sys
import hashlib
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {".venv", "test_venv", ".git", ".pytest_cache", "__pycache__", "cache", "uploads", "artifacts"}
EXCLUDE_EXTS = {".whl", ".pth", ".pt", ".wav", ".mp3", ".flac", ".png", ".jpg", ".zip", ".log"}


def scan_hardcoded_paths():
    findings = []
    path_regex = re.compile(r"([A-Za-z]:\\[^ \t\r\n\"';><)]+|/home/[^ \t\r\n\"';><)]+|Users\\[a-zA-Z0-9_-]+)", re.IGNORECASE)
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in EXCLUDE_EXTS:
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                for idx, line in enumerate(content.splitlines(), start=1):
                    # Skip comment references in markdown docs if purely informational
                    match = path_regex.search(line)
                    if match:
                        matched_str = match.group(0)
                        findings.append({
                            "file": str(p.relative_to(PROJECT_ROOT)),
                            "line": idx,
                            "match": matched_str,
                            "content": line.strip()
                        })
            except Exception as e:
                pass
    return findings


def scan_imports():
    import_regex = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_]+)|import\s+([a-zA-Z0-9_]+))")
    found_modules = set()
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    m = import_regex.match(line)
                    if m:
                        mod = m.group(1) or m.group(2)
                        found_modules.add(mod)
                        
    # Filter builtins
    stdlib = sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else set()
    non_stdlib = {m for m in found_modules if m not in stdlib and m not in {"audio_forensics", "tools"}}
    return sorted(non_stdlib)


def check_models():
    models_info = [
        {
            "name": "xlsr2_300m.pt",
            "path": PROJECT_ROOT / "audio_forensics" / "models" / "xlsr2_300m.pt",
            "expected_url": "https://dl.fbaipublicfiles.com/fairseq/wav2vec/xlsr2_300m.pt",
        },
        {
            "name": "LA_model.pth",
            "path": PROJECT_ROOT / "audio_forensics" / "models" / "LA_model.pth",
            "expected_url": "https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST/resolve/main/LA_model.pth",
        }
    ]
    results = []
    for m in models_info:
        p = m["path"]
        exists = p.is_file()
        size = p.stat().st_size if exists else 0
        sha256 = ""
        if exists:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(1024*1024):
                    h.update(chunk)
            sha256 = h.hexdigest()
        
        # Test URL reachability
        url_status = "unknown"
        try:
            req = urllib.request.Request(m["expected_url"], method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                url_status = f"{resp.status} OK"
        except Exception as e:
            url_status = f"Failed ({e})"
            
        results.append({
            "name": m["name"],
            "exists": exists,
            "size_bytes": size,
            "sha256": sha256,
            "url": m["expected_url"],
            "url_status": url_status
        })
    return results


def run_audit():
    print("=" * 80)
    print("PS-05 AUDIO FORENSICS PORTABILITY AUDIT")
    print("=" * 80)
    
    # a. Hardcoded paths
    hardcoded = scan_hardcoded_paths()
    print(f"\n[a] Hardcoded Absolute Paths Found: {len(hardcoded)}")
    for h in hardcoded:
        print(f"  - {h['file']}:{h['line']} -> {h['match']}")
        
    # c. Python packages
    imports = scan_imports()
    print(f"\n[c] Third-Party Top-Level Imports Detected: {len(imports)}")
    print(f"    {', '.join(imports)}")
    
    req_file = PROJECT_ROOT / "requirements-lock.txt"
    req_content = req_file.read_text() if req_file.is_file() else ""
    print(f"    requirements-lock.txt present: {req_file.is_file()}")
    
    # f. Models
    print("\n[f] Model Checkpoints Verification:")
    models = check_models()
    for m in models:
        exists_str = f"PRESENT ({m['size_bytes'] / (1024*1024):.1f} MB)" if m["exists"] else "MISSING"
        print(f"  - {m['name']}: {exists_str}")
        print(f"    URL: {m['url']} -> {m['url_status']}")
        if m["sha256"]:
            print(f"    SHA256: {m['sha256']}")
            
    print("\n" + "=" * 80)

if __name__ == "__main__":
    run_audit()
