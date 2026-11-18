from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .. import config
from ..jobs import Job, manager
from .audio.chunking import SR, compute_chunks, load_audio
from .audio.ports import AsrResult, Segment, Turn
from .engines.base import ASREngine, DiarizationEngine
from .engines.speaker_assignment import assign_word_speakers


def resolve_engines(cfg: dict[str, Any], log: Callable[[str], None]) -> tuple[ASREngine, DiarizationEngine]:
    from .engines.asr.whisperx import WhisperXEngine
    from .engines.diar.pyannote import PyannoteEngine

    return WhisperXEngine(log=log), PyannoteEngine()


def run(project_id: str, audio_path: Path, job: Job) -> None:
    cfg = config.load_config()
    cfg_asr, cfg_diar = cfg["asr"], cfg["diar"]
    started_at = time.time()
    asr_engine, diar_engine = resolve_engines(cfg, lambda line: job.log_line(manager, line))
    check_cancel = job.check_cancel
    last_progress = job.progress

    def update_progress(stage: str, progress: float, detail: str | None) -> None:
        nonlocal last_progress
        progress = max(last_progress, min(100.0, max(0.0, progress)))
        last_progress = progress
        manager.update(job, stage=stage, progress=progress, detail=detail)

    check_cancel()
    manager.update(
        job,
        stage="Cargando modelo",
        detail=f"{cfg_asr['model']} ({cfg_asr['device']}, {cfg_asr['compute_type']})",
    )
    job.log_line(manager, f"Cargando modelo Whisper '{cfg_asr['model']}' en {cfg_asr['device']}…")
    asr_engine.load(cfg_asr, check_cancel=check_cancel)
    check_cancel()

    manager.update(job, stage="Leyendo audio", detail="Decodificando a 16 kHz…")
    check_cancel()
    audio_buffer = load_audio(audio_path)
    check_cancel()
    audio = audio_buffer.samples
    duration = audio_buffer.duration
    job.log_line(manager, f"Audio: {duration / 60:.1f} min")

    chunks = compute_chunks(audio, cfg_asr["chunk_minutes"])
    job.log_line(manager, f"{len(chunks)} tramos de ~{cfg_asr['chunk_minutes']} min")
    segments: list[Segment] = []
    language = cfg_asr["language"] or "es"

    for i, (start, end) in enumerate(chunks):
        check_cancel()
        update_progress(
            f"Transcribiendo ({i + 1}/{len(chunks)})",
            5 + (i / len(chunks)) * 55,
            f"min {start / 60:.0f}–{end / 60:.0f}",
        )
        chunk_audio = audio[int(start * SR):int(end * SR)]
        result: AsrResult = asr_engine.transcribe(chunk_audio, check_cancel=check_cancel)
        check_cancel()
        language = result.language or language
        for segment in result.segments:
            segment.start += start
            segment.end += start
            for word in segment.words:
                if word.start is not None:
                    word.start += start
                if word.end is not None:
                    word.end += start
            if segment.text.strip():
                segments.append(segment)

    speakers_found: list[str] = []
    turns: list[Turn] = []
    if cfg_diar.get("hf_token"):
        check_cancel()
        update_progress("Diarizando", 62, "Identificando voces…")
        job.log_line(manager, "Ejecutando diarización pyannote…")
        diar_engine.load(cfg_diar, check_cancel=check_cancel)
        check_cancel()

        def on_diar_progress(stage: str, fraction: float, detail: str) -> None:
            check_cancel()
            update_progress("Diarizando", 62 + fraction * 32, detail)

        check_cancel()
        turns = diar_engine.diarize(audio_path, on_diar_progress, check_cancel=check_cancel)
        check_cancel()
        speakers_found = sorted({turn.speaker for turn in turns})
        if turns:
            update_progress("Asignando hablantes", 95, f"{len(speakers_found)} voces detectadas")
            for segment in segments:
                check_cancel()
                segment.words = assign_word_speakers(segment.words, turns)
                if segment.words:
                    segment.speaker = next((word.speaker for word in segment.words if word.speaker), segment.speaker)
            check_cancel()
    else:
        job.log_line(manager, "Sin token de HuggingFace: se omite la diarización (configúralo en Ajustes)")

    check_cancel()
    update_progress("Guardando transcripción", 98, None)
    out_segments = []
    for idx, segment in enumerate(segments):
        words = [
            {"word": word.word, "start": word.start, "end": word.end, "speaker": word.speaker}
            for word in segment.words
        ]
        seg_speaker = segment.speaker or (words[0]["speaker"] if words and words[0]["speaker"] else None)
        out_segments.append(
            {
                "id": idx,
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "speaker": seg_speaker,
                "text": segment.text.strip(),
                "words": words,
                "edited": False,
                "original_text": None,
            }
        )

    if not speakers_found:
        for segment in out_segments:
            segment["speaker"] = None

    transcript_doc = {
        "language": language,
        "duration": round(duration, 2),
        "model": {
            "engine": asr_engine.info().id,
            "model": cfg_asr["model"],
            "whisper_model": cfg_asr["model"],
            "device": cfg_asr["device"],
            "compute_type": cfg_asr["compute_type"],
            "diarized": bool(cfg_diar.get("hf_token")),
        },
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "speakers": [{"id": speaker, "name": None, "clips": []} for speaker in speakers_found],
        "segments": out_segments,
    }
    check_cancel()
    config.save_json(project_id, "transcript.json", transcript_doc)
    check_cancel()
    config.save_meta(project_id, {"stage": "speakers", "duration": round(duration, 1), "language": language})
    check_cancel()
    job.log_line(manager, f"Listo: {len(out_segments)} segmentos, {len(speakers_found)} hablantes en {time.time() - started_at:.0f}s")
