"""
Root standalone launcher forwarding to ai_image_detection.main_standalone
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MODULE_DIR = ROOT_DIR / "ai_image_detection"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from ai_image_detection.main_standalone import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_standalone:app", host="127.0.0.1", port=8000, reload=True)
