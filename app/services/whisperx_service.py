"""Transcripción con WhisperX por tramos, con progreso y cortes en silencios."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np

from .. import config
from ..jobs import Job, JobCancelled

SR = 16000

_model_cache: dict = {}


def load_asr_model(cfg_asr: dict):
    import whisperx

    key = ("asr", cfg_asr["model"], cfg_asr["device"], cfg_asr["compute_type"])
    if key not in _model_cache:
        _model_cache[key] = whisperx.load_model(
            cfg_asr["model"],
            cfg_asr["device"],
            compute_type=cfg_asr["compute_type"],
            language=cfg_asr["language"] or None,
        )
    return _model_cache[key]


def load_alignment_model(language: str):
    import whisperx

    key = ("align", language)
    if key not in _model_cache:
        model_a, metadata = whisperx.load_align_model(language_code=language, device="cpu")
        _model_cache[key] = (model_a, metadata)
    return _model_cache[key]


def snap_boundary(audio: np.ndarray, target_sec: float, search: float = 3.0, frame_ms: int = 30) -> float:
    """Busca el punto de mínima energía (silencio) cerca de target_sec."""
    frame = int(SR * frame_ms / 1000)
    lo = max(0, int((target_sec - search) * SR))
    hi = min(len(audio), int((target_sec + search) * SR))
    if hi - lo < frame * 3:
        return target_sec
    seg = audio[lo:hi]
    n = len(seg) // frame
    energy = (seg[: n * frame].reshape(n, frame) ** 2).mean(axis=1)
    idx = int(energy.argmin())
    return (lo + idx * frame + frame / 2) / SR


def compute_chunks(audio: np.ndarray, chunk_minutes: int) -> list[tuple[float, float]]:
    total = len(audio) / SR
    win = chunk_minutes * 60
    raw = [x * win for x in range(0, int(total // win) + 1) if x * win > 0]
    raw = [s for s in raw if s < total - 10]
    cuts = [0.0] + [snap_boundary(audio, s) for s in raw] + [total]
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1) if cuts[i + 1] - cuts[i] > 0.5]


def transcribe_and_diarize(project_id: str, audio_path: Path, job: Job) -> None:
    import torch  # noqa: F401  (asegura backend antes de whisperx)
    import whisperx

    from ..ffmpeg_utils import get_ffmpeg
    from ..jobs import manager
    from .diarization import diarize_to_dataframe

    cfg = config.load_config()
    cfg_asr, cfg_diar = cfg["asr"], cfg["diar"]

    get_ffmpeg()  # asegura PATH para whisperx.load_audio

    t0 = time.time()
    manager.update(job, stage="Cargando modelo", detail=f"{cfg_asr['model']} ({cfg_asr['device']}, {cfg_asr['compute_type']})")
    job.log_line(manager, f"Cargando modelo Whisper '{cfg_asr['model']}' en {cfg_asr['device']}…")
    model = load_asr_model(cfg_asr)

    manager.update(job, stage="Leyendo audio", detail="Decodificando a 16 kHz…")
    audio = whisperx.load_audio(str(audio_path))
    duration = len(audio) / SR
    job.log_line(manager, f"Audio: {duration/60:.1f} min")

    chunks = compute_chunks(audio, cfg_asr["chunk_minutes"])
    job.log_line(manager, f"{len(chunks)} tramos de ~{cfg_asr['chunk_minutes']} min")

    align_state: dict = {}
    segments: list[dict] = []

    for i, (start, end) in enumerate(chunks):
        job.check_cancel()
        manager.update(
            job,
            stage=f"Transcribiendo ({i + 1}/{len(chunks)})",
            progress=5 + (i / len(chunks)) * 55,
            detail=f"min {start/60:.0f}–{end/60:.0f}",
        )
        chunk_audio = audio[int(start * SR): int(end * SR)]
        result = model.transcribe(
            chunk_audio,
            batch_size=cfg_asr["batch_size"],
            language=cfg_asr["language"] or None,
        )
        language = result.get("language") or cfg_asr["language"] or "es"

        if "align" not in align_state:
            try:
                align_state["align"] = load_alignment_model(language)
                align_state["language"] = language
                job.log_line(manager, f"Modelo de alineación cargado (idioma: {language})")
            except Exception as exc:  # noqa: BLE001
                job.log_line(manager, f"Alineación no disponible ({exc}); se usarán tiempos del ASR")
                align_state["align"] = None

        if align_state["align"]:
            try:
                aligned = whisperx.align(
                    result["segments"],
                    align_state["align"][0],
                    align_state["align"][1],
                    chunk_audio,
                    "cpu",
                    return_char_alignments=False,
                )["segments"]
            except Exception as exc:  # noqa: BLE001
                job.log_line(manager, f"Alineación fallida en tramo {i + 1}: {exc}")
                aligned = result["segments"]
        else:
            aligned = result["segments"]

        for seg in aligned:
            seg["start"] = float(seg["start"]) + start
            seg["end"] = float(seg["end"]) + start
            for w in seg.get("words", []) or []:
                if w.get("start") is not None:
                    w["start"] = float(w["start"]) + start
                if w.get("end") is not None:
                    w["end"] = float(w["end"]) + start
            if seg.get("text", "").strip():
                segments.append(seg)

    # ---------- diarización ----------
    speakers_found: list[str] = []
    diarize_df = None
    if cfg_diar.get("hf_token"):
        job.check_cancel()
        manager.update(job, stage="Diarizando", progress=62, detail="Identificando voces…")
        job.log_line(manager, "Ejecutando diarización pyannote…")

        def on_diar_progress(pct: float, detail: str) -> None:
            job.check_cancel()
            manager.update(job, stage="Diarizando", progress=62 + pct * 0.32, detail=detail)

        diarize_df = diarize_to_dataframe(audio_path, cfg_diar, on_diar_progress)
        if diarize_df is not None and len(diarize_df):
            speakers_found = sorted(diarize_df["speaker"].unique().tolist())
            manager.update(job, stage="Asignando hablantes", progress=95, detail=f"{len(speakers_found)} voces detectadas")

            transcript = {"segments": segments, "language": align_state.get("language", cfg_asr["language"] or "es")}
            try:
                from whisperx.diarize import assign_word_speakers

                transcript = assign_word_speakers(diarize_df, transcript)
                segments = transcript["segments"]
            except Exception as exc:  # noqa: BLE001
                job.log_line(manager, f"No se pudieron asignar hablantes: {exc}")
    else:
        job.log_line(manager, "Sin token de HuggingFace: se omite la diarización (configúralo en Ajustes)")

    # ---------- construir transcript.json ----------
    manager.update(job, stage="Guardando transcripción", progress=98)
    out_segments = []
    for idx, seg in enumerate(segments):
        words = [
            {"word": w.get("word", ""), "start": w.get("start"), "end": w.get("end"), "speaker": w.get("speaker")}
            for w in (seg.get("words") or [])
        ]
        seg_speaker = seg.get("speaker") or (words[0].get("speaker") if words and words[0].get("speaker") else None)
        out_segments.append(
            {
                "id": idx,
                "start": round(float(seg["start"]), 3),
                "end": round(float(seg["end"]), 3),
                "speaker": seg_speaker,
                "text": seg.get("text", "").strip(),
                "words": words,
                "edited": False,
                "original_text": None,
            }
        )

    if not speakers_found and out_segments:
        out_segments = [{**s, "speaker": None} for s in out_segments]

    transcript_doc = {
        "language": align_state.get("language", cfg_asr["language"] or "es"),
        "duration": round(duration, 2),
        "model": {
            "whisper_model": cfg_asr["model"],
            "device": cfg_asr["device"],
            "compute_type": cfg_asr["compute_type"],
            "diarized": bool(cfg_diar.get("hf_token")),
        },
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "speakers": [{"id": s, "name": None, "clips": []} for s in speakers_found],
        "segments": out_segments,
    }
    config.save_json(project_id, "transcript.json", transcript_doc)
    config.save_meta(project_id, {"stage": "speakers", "duration": round(duration, 1), "language": transcript_doc["language"]})
    job.log_line(manager, f"Listo: {len(out_segments)} segmentos, {len(speakers_found)} hablantes en {time.time() - t0:.0f}s")
