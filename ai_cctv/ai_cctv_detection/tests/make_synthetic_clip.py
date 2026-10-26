"""Synthetic CCTV video clip generator for automated testing."""

from pathlib import Path
import sys

# Re-export from root tests
root_tests = Path(__file__).resolve().parent.parent.parent / "tests"
if str(root_tests) not in sys.path:
    sys.path.insert(0, str(root_tests))

from make_synthetic_clip import create_synthetic_clip, main

if __name__ == "__main__":
    main()
