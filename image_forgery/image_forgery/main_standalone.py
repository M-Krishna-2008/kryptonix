"""
Standalone FastAPI application for solo testing of the image_forgery module.
Mounts the module router and serves static UI files.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .router import router
except ImportError:
    from router import router

MODULE_ROOT = Path(__file__).resolve().parent
STATIC_DIR = MODULE_ROOT / "static"

app = FastAPI(
    title="PS-05 Image Forgery Forensic Module (Standalone)",
    version="1.0"
)

# Mount contractual router
app.include_router(router)

# Mount static files
app.mount("/image_forgery-static", StaticFiles(directory=str(STATIC_DIR)), name="image_forgery-static")


@app.get("/")
async def root():
    """Serve standalone module UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
