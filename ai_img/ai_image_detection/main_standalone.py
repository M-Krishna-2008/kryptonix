"""
Standalone FastAPI application for solo testing the ai_image_detection module.
Mounts the module router and serves static assets.
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

MODULE_DIR = Path(__file__).resolve().parent
STATIC_DIR = MODULE_DIR / "static"

# Ensure module is discoverable on python path
if str(MODULE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR.parent))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

try:
    from .router import router as ai_image_detection_router
except (ImportError, ValueError):
    from router import router as ai_image_detection_router

app = FastAPI(
    title="PS-05 AI Image Detection (UnivFD) Standalone",
    description="Stand-alone harness for local forensic AI image authenticity verification",
    version="1.0"
)

# Mount module API router
app.include_router(ai_image_detection_router)

# Mount module static assets
app.mount("/ai_image_detection-static", StaticFiles(directory=str(STATIC_DIR), html=True), name="ai_image_detection_static")


@app.get("/")
async def root():
    """Redirect root requests directly to module static index harness."""
    return RedirectResponse(url="/ai_image_detection-static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_standalone:app", host="127.0.0.1", port=8000, reload=True)
