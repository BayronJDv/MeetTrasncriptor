"""Proyectos: creación (subida de audio), listado, borrado y streaming de audio."""
from __future__ import annotations

import re
import shutil
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import config
from ..ffmpeg_utils import make_playback_copy, probe_duration

router = APIRouter(prefix="/api/projects", tags=["projects"])

ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".mp4", ".mkv", ".webm", ".mov", ".avi"}


def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w\s.\-()áéíóúÁÉÍÓÚñÑ]", "_", name).strip()
    return name[:120] or "audio"


@router.get("")
def list_projects() -> list[dict]:
    return config.list_projects()


@router.post("")
async def create_project(
    file: UploadFile = File(...),
    name: str = Form(""),
) -> dict:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Formato no soportado: {ext}. Permitidos: {', '.join(sorted(ALLOWED_EXT))}")

    project_id = config.new_project_id()
    pdir = config.project_dir(project_id)
    audio_name = f"audio_original{ext}"
    dest = pdir / audio_name

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(8 * 1024 * 1024):
            size += len(chunk)
            out.write(chunk)
    if size == 0:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(400, "El archivo está vacío")

    playback_ok = make_playback_copy(dest, pdir / "audio_playback.mp3")
    duration = probe_duration(dest)

    meta = config.save_meta(
        project_id,
        {
            "id": project_id,
            "name": _safe_name(name or file.filename.rsplit(".", 1)[0]),
            "original_filename": file.filename,
            "audio_file": audio_name,
            "playback_file": "audio_playback.mp3" if playback_ok else audio_name,
            "size": size,
            "duration": duration,
            "stage": "created",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    return meta


@router.get("/{project_id}")
def get_project(project_id: str) -> dict:
    meta = config.load_meta(project_id)
    if not meta:
        raise HTTPException(404, "Proyecto no encontrado")
    meta["has_transcript"] = (config.PROJECTS_DIR / project_id / "transcript.json").exists()
    meta["has_review"] = (config.PROJECTS_DIR / project_id / "review.json").exists()
    meta["has_meeting"] = (config.PROJECTS_DIR / project_id / "meeting.json").exists()
    meta["has_report"] = (config.PROJECTS_DIR / project_id / "informe.md").exists()
    return meta


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    pdir = config.PROJECTS_DIR / project_id
    if not pdir.exists():
        raise HTTPException(404, "Proyecto no encontrado")
    shutil.rmtree(pdir)
    return {"ok": True}


@router.get("/{project_id}/audio")
def get_audio(project_id: str) -> FileResponse:
    meta = config.load_meta(project_id)
    if not meta:
        raise HTTPException(404, "Proyecto no encontrado")
    # copia de reproducción (mp3) para seek fluido; fallback al original
    path = config.PROJECTS_DIR / project_id / meta.get("playback_file", meta["audio_file"])
    if not path.exists():
        path = config.PROJECTS_DIR / project_id / meta["audio_file"]
    return FileResponse(path, media_type="audio/mpeg" if path.suffix == ".mp3" else "application/octet-stream")
