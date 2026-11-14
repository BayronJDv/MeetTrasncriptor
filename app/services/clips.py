"""Extracción de clips de voz por hablante (wav 16 kHz, carga instantánea)."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..ffmpeg_utils import extract_clip
from .diarization import suggest_clips


def generate_speaker_clips(project_id: str, clips_per_speaker: int | None = None) -> list[dict]:
    """Genera clips sugeridos para cada hablante y actualiza transcript.json."""
    transcript = config.load_json(project_id, "transcript.json")
    if not transcript:
        raise RuntimeError("El proyecto aún no tiene transcripción")

    cfg = config.load_config()
    n = clips_per_speaker or cfg["diar"].get("clips_per_speaker", 4)
    project_path = config.project_dir(project_id)
    clips_dir = project_path / "clips"
    clips_dir.mkdir(exist_ok=True)

    # audio de mayor calidad disponible (el original, no el mp3 de reproducción)
    meta = config.load_meta(project_id) or {}
    source = project_path / (meta.get("audio_file") or "")
    if not source.exists():
        source = project_path / "audio_playback.mp3"

    speakers = transcript.get("speakers", [])
    for speaker in speakers:
        sid = speaker["id"]
        suggestions = suggest_clips(transcript["segments"], sid, n)
        clips = []
        for i, c in enumerate(suggestions, start=1):
            fname = f"{sid}_clip{i}.wav"
            dest = clips_dir / fname
            ok = source.exists() and extract_clip(source, c["start"], c["end"], dest)
            clips.append(
                {
                    "file": fname if ok else None,
                    "start": c["start"],
                    "end": c["end"],
                    "duration": c["duration"],
                    "text": c["text"][:120],
                }
            )
        speaker["clips"] = clips

    config.save_json(project_id, "transcript.json", transcript)
    return speakers


def clips_manifest(project_id: str) -> dict:
    """Manifiesto de clips para el frontend (sin releer transcript completo)."""
    transcript = config.load_json(project_id, "transcript.json") or {}
    speakers = transcript.get("speakers", [])
    manifest = {}
    for s in speakers:
        manifest[s["id"]] = {
            "name": s.get("name"),
            "clips": s.get("clips", []),
        }
    return manifest
