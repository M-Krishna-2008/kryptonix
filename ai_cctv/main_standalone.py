"""Standalone FastAPI application for AI CCTV Detection module.

Mounts the module's router, serves static assets, and displays the UI at root /.
Run directly with:
    uvicorn main_standalone:app --host 127.0.0.1 --port 8000
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

# Import router from package
from ai_cctv_detection.router import router

app = FastAPI(
    title="PS-05: AI CCTV Detection Standalone",
    description="Detects whether CCTV video clips are real or AI-generated using fine-tuned YOLO11-cls.",
    version="1.0.0",
)

# Enable CORS for local testing and multi-module embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount module API router
app.include_router(router)

# Locate static directory
MODULE_DIR = Path(__file__).resolve().parent / "ai_cctv_detection"
STATIC_DIR = MODULE_DIR / "static"

if not STATIC_DIR.is_dir():
    # Handle if run from inside ai_cctv_detection/
    STATIC_DIR = Path(__file__).resolve().parent / "static"

# Mount static files under the standard module namespace (Integration Contract)
app.mount("/ai_cctv_detection-static", StaticFiles(directory=str(STATIC_DIR)), name="ai_cctv_detection_static")


@app.get("/module.css", include_in_schema=False)
def serve_css():
    """Serve CSS directly at root for standalone mode."""
    return FileResponse(STATIC_DIR / "module.css", media_type="text/css")


@app.get("/module.js", include_in_schema=False)
def serve_js():
    """Serve JS directly at root for standalone mode."""
    return FileResponse(STATIC_DIR / "module.js", media_type="application/javascript")


@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon():
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
def serve_index():
    """Serve module standalone UI."""
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_standalone:app", host="127.0.0.1", port=8000, reload=True)
