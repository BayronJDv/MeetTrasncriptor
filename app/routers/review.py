"""Revisión asistida por IA: iniciar análisis, consultar y resolver sugerencias."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config
from ..jobs import manager
from ..schemas import SuggestionUpdate
from ..services.llm.review import (
    accept_suggestion,
    reject_suggestion,
    review_suggestion_state,
    run_review_job,
)

router = APIRouter(prefix="/api/projects/{project_id}/review", tags=["review"])


@router.post("/start")
def start_review(project_id: str) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise HTTPException(400, "El proyecto no tiene transcripción")

    job = manager.submit("review", project_id, lambda job: run_review_job(project_id, job))
    return job.snapshot()


@router.get("")
def get_review(project_id: str) -> dict:
    state = review_suggestion_state(project_id)
    job = manager.running_for_project(project_id)
    if job and job.kind == "review":
        state["job"] = job.snapshot()
    return state


@router.patch("/suggestions/{suggestion_id}")
def update_suggestion(project_id: str, suggestion_id: str, body: SuggestionUpdate) -> dict:
    if body.status == "accepted":
        return accept_suggestion(project_id, suggestion_id, None)
    if body.status == "edited":
        if not (body.replacement or "").strip():
            raise HTTPException(400, "Falta el texto de reemplazo")
        return accept_suggestion(project_id, suggestion_id, body.replacement.strip())
    if body.status == "rejected":
        return reject_suggestion(project_id, suggestion_id)
    raise HTTPException(400, f"Estado no soportado: {body.status}")
