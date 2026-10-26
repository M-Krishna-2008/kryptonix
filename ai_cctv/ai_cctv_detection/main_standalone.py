"""Standalone FastAPI application inside module folder."""

import sys
from pathlib import Path

parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from ai_cctv_detection.router import router

app = FastAPI(
    title="PS-05: AI CCTV Detection Standalone",
    description="Detects whether CCTV video clips are real or AI-generated using fine-tuned YOLO11-cls.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/ai_cctv_detection-static", StaticFiles(directory=str(STATIC_DIR)), name="ai_cctv_detection_static")


@app.get("/module.css", include_in_schema=False)
def serve_css():
    return FileResponse(STATIC_DIR / "module.css", media_type="text/css")


@app.get("/module.js", include_in_schema=False)
def serve_js():
    return FileResponse(STATIC_DIR / "module.js", media_type="application/javascript")


@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon():
    return Response(status_code=204)


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_standalone:app", host="127.0.0.1", port=8000, reload=True)
