"""Diarización de hablantes con pyannote vía whisperx.DiarizationPipeline (3.8).

- Progreso nativo (0-100) conectado a la barra de la UI.
- Decodificación en memoria con ffmpeg (sin depender de torchcodec).
- Intenta en GPU si hay torch-CUDA y hace fallback automático a CPU.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


def _is_gpu_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(k in text for k in ("cuda", "nvidia", "out of memory", "gpu", "sm_"))


def _pick_device(cfg_diar: dict, progress_cb: Callable[[float, str], None]) -> str:
    import torch

    want = cfg_diar.get("device", "auto")
    available = torch.cuda.is_available()
    if want == "auto":
        return "cuda" if available else "cpu"
    if want == "cuda" and not available:
        progress_cb(0.0, "Se pidió GPU pero torch no tiene CUDA: usando CPU")
        return "cpu"
    return want


def diarize_to_dataframe(
    audio_path: Path,
    cfg_diar: dict,
    progress_cb: Callable[[float, str], None],
) -> pd.DataFrame | None:
    """Devuelve un DataFrame start/end/speaker de los turnos de voz detectados."""
    import torch

    from whisperx.diarize import DiarizationPipeline

    hf_token = cfg_diar.get("hf_token") or ""
    device = _pick_device(cfg_diar, progress_cb)
    progress_cb(0.0, f"Cargando pyannote en {device.upper()}…")

    def run(device_name: str) -> pd.DataFrame:
        pipeline = DiarizationPipeline(token=hf_token or None, device=device_name)

        def on_progress(pct: float) -> None:
            progress_cb(min(1.0, max(0.0, pct / 100.0)), f"Diarizando ({pct:.0f} %)")

        kwargs: dict = {}
        if cfg_diar.get("min_speakers"):
            kwargs["min_speakers"] = cfg_diar["min_speakers"]
        if cfg_diar.get("max_speakers"):
            kwargs["max_speakers"] = cfg_diar["max_speakers"]
        return pipeline(str(audio_path), progress_callback=on_progress, **kwargs)

    try:
        return run(device)
    except (torch.cuda.OutOfMemoryError, RuntimeError, AssertionError) as exc:
        if device != "cpu" and _is_gpu_error(exc):
            progress_cb(0.0, f"GPU sin memoria ({exc}): reintentando en CPU…")
            return run("cpu")
        raise


def suggest_clips(
    segments: list[dict],
    speaker_id: str,
    n_clips: int,
    min_gap: float = 30.0,
) -> list[dict]:
    """Elige los N mejores fragmentos de un hablante: largos y separados entre sí."""
    candidates = [
        {"start": s["start"], "end": s["end"], "duration": s["end"] - s["start"], "text": s["text"]}
        for s in segments
        if s.get("speaker") == speaker_id and (s["end"] - s["start"]) >= 1.5 and s.get("text")
    ]
    candidates.sort(key=lambda c: c["duration"], reverse=True)
    picked: list[dict] = []
    for c in candidates:
        if all(abs(c["start"] - p["start"]) >= min_gap for p in picked):
            picked.append(c)
        if len(picked) >= n_clips:
            break
    if not picked:  # audio corto: relajar separación
        picked = candidates[:n_clips]
    picked.sort(key=lambda c: c["start"])
    return [
        {"start": round(p["start"], 2), "end": round(p["end"], 2), "duration": round(p["duration"], 2), "text": p["text"]}
        for p in picked
    ]
