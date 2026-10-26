from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from audio_forensics.router import router
from audio_forensics.config import STATIC_DIR

app = FastAPI(
    title="PS-05 Audio Forensics Platform",
    description="Local Speech Authenticity, Tampering & Deepfake Detection",
    version="1.0.0",
)

# Mount module API router under standard prefix /api/audio_forensics
app.include_router(router)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serves the standalone module UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_standalone:app", host="127.0.0.1", port=8000, reload=True)
