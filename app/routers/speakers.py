"""Hablantes: transcripción, clips sugeridos, renombrado y edición de segmentos."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config
from ..jobs import manager
from ..schemas import SegmentPatch, SpeakerRename
from ..services.clips import generate_speaker_clips

router = APIRouter(prefix="/api/projects/{project_id}", tags=["speakers"])


@router.get("/transcript")
def get_transcript(project_id: str) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if transcript is None:
        raise HTTPException(404, "Aún no hay transcripción")
    return transcript


@router.get("/speakers")
def get_speakers(project_id: str) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if transcript is None:
        raise HTTPException(404, "Aún no hay transcripción")
    return {
        "speakers": transcript.get("speakers", []),
        "segments": transcript.get("segments", []),
        "duration": transcript.get("duration"),
    }


@router.post("/speakers/clips")
def make_clips(project_id: str) -> dict:
    if manager.running_for_project(project_id):
        raise HTTPException(409, "Hay un trabajo en curso para este proyecto")
    speakers = generate_speaker_clips(project_id)
    return {"speakers": speakers}


@router.post("/speakers/rename")
def rename_speaker(project_id: str, body: SpeakerRename) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if transcript is None:
        raise HTTPException(404, "Aún no hay transcripción")
    speaker = next((s for s in transcript["speakers"] if s["id"] == body.speaker_id), None)
    if speaker is None:
        raise HTTPException(404, "Hablante no encontrado")
    speaker["name"] = (body.name or "").strip() or None
    config.save_json(project_id, "transcript.json", transcript)
    return speaker


@router.patch("/segments/{segment_id}")
def patch_segment(project_id: str, segment_id: int, body: SegmentPatch) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if transcript is None:
        raise HTTPException(404, "Aún no hay transcripción")
    seg = next((s for s in transcript["segments"] if s["id"] == segment_id), None)
    if seg is None:
        raise HTTPException(404, "Segmento no encontrado")
    if body.text is not None:
        if seg.get("original_text") is None:
            seg["original_text"] = seg["text"]
        seg["text"] = body.text.strip()
        seg["edited"] = True
    if body.speaker is not None:
        valid = {s["id"] for s in transcript["speakers"]}
        if body.speaker not in valid:
            raise HTTPException(400, f"Hablante inválido: {body.speaker}")
        seg["speaker"] = body.speaker
    config.save_json(project_id, "transcript.json", transcript)
    return seg


@router.get("/clips/{speaker_id}/{filename}")
def get_clip(project_id: str, speaker_id: str, filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Nombre inválido")
    path = config.PROJECTS_DIR / project_id / "clips" / filename
    if not path.exists():
        raise HTTPException(404, "Clip no encontrado")
    return FileResponse(path, media_type="audio/wav")
