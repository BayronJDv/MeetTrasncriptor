"""Estructura de la reunión: análisis automático y edición del esquema."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config
from ..jobs import manager
from ..schemas import MeetingPatch
from ..services.llm.meeting import meeting_state, run_meeting_job

router = APIRouter(prefix="/api/projects/{project_id}/meeting", tags=["meeting"])


@router.post("/analyze")
def analyze_meeting(project_id: str) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise HTTPException(400, "El proyecto no tiene transcripción")
    job = manager.submit("meeting", project_id, lambda job: run_meeting_job(project_id, job))
    return job.snapshot()


@router.get("")
def get_meeting(project_id: str) -> dict:
    state = meeting_state(project_id)
    job = manager.running_for_project(project_id)
    if job and job.kind == "meeting":
        state["job"] = job.snapshot()
    return state


@router.put("")
def save_meeting(project_id: str, body: MeetingPatch) -> dict:
    state = {"status": "done", "sections": [s.model_dump() for s in body.sections]}
    config.save_json(project_id, "meeting.json", state)
    return state
