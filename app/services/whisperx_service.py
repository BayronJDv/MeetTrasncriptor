"""Compatibilidad temporal para iniciar la transcripción desde el router actual."""
from __future__ import annotations

from pathlib import Path

from ..jobs import Job
from .transcription import run


def transcribe_and_diarize(project_id: str, audio_path: Path, job: Job) -> None:
    run(project_id, audio_path, job)
