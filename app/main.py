"""Aplicación FastAPI: API + frontend estático (web/dist)."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .jobs import manager
from .routers import llm, meeting, projects, report, review, settings, speakers, transcribe

BASE_DIR = config.BASE_DIR
WEB_DIST = BASE_DIR / "web" / "dist"

app = FastAPI(title="Transcriptor de reuniones", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    projects.router,
    transcribe.router,
    speakers.router,
    review.router,
    meeting.router,
    report.router,
    settings.router,
    llm.router,
):
    app.include_router(r)


@app.on_event("startup")
async def startup() -> None:
    config.ensure_dirs()
    loop = asyncio.get_running_loop()
    manager.start(loop)
    # prepara el binario de ffmpeg en PATH para whisperx
    try:
        from .ffmpeg_utils import get_ffmpeg

        get_ffmpeg()
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: ffmpeg no disponible aún ({exc})")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = WEB_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(404, "Frontend no compilado: ejecuta 'npm run build' en web/")
else:

    @app.get("/", include_in_schema=False)
    def no_frontend() -> dict:
        return {
            "api": "ok",
            "hint": "El frontend no está compilado. Ejecuta: cd web && npm install && npm run build",
        }
