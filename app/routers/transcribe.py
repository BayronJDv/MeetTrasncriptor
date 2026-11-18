"""Transcripción: iniciar el trabajo, eventos SSE de progreso y cancelación."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from .. import config
from ..jobs import manager
from ..services import transcription

router = APIRouter(prefix="/api", tags=["transcribe"])


@router.post("/projects/{project_id}/transcribe")
def start_transcription(project_id: str) -> dict:
    meta = config.load_meta(project_id)
    if not meta:
        raise HTTPException(404, "Proyecto no encontrado")
    audio_path = config.PROJECTS_DIR / project_id / meta["audio_file"]
    if not audio_path.exists():
        raise HTTPException(400, "El archivo de audio no existe")

    def run(job) -> None:
        transcription.run(project_id, audio_path, job)

    job = manager.submit("transcribe", project_id, run)
    return job.snapshot()


@router.get("/projects/{project_id}/events")
async def project_events(project_id: str) -> EventSourceResponse:
    async def gen():
        queue = manager.subscribe(project_id)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"data": payload}
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}
        finally:
            manager.unsubscribe(project_id, queue)

    return EventSourceResponse(gen())


@router.get("/projects/{project_id}/job")
def last_job(project_id: str) -> dict:
    job = manager.last_job(project_id)
    if not job:
        stored = config.load_json(project_id, "job.json")
        if stored:
            return stored
        return {"status": "none"}
    return job.snapshot()


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not manager.cancel(job_id):
        raise HTTPException(404, "Trabajo no encontrado o ya finalizado")
    return {"ok": True}
