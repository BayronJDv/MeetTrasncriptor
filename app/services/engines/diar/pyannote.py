from __future__ import annotations

from pathlib import Path
from typing import Any

from ...audio.ports import EngineInfo, ProgressFn, Turn


def _is_gpu_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(key in text for key in ("cuda", "nvidia", "out of memory", "gpu", "sm_"))


class PyannoteEngine:
    def __init__(self):
        self._torch = None
        self._pipeline_class = None
        self._config: dict[str, Any] = {}

    def load(self, config: dict[str, Any]) -> None:
        import torch
        from whisperx.diarize import DiarizationPipeline

        self._torch = torch
        self._pipeline_class = DiarizationPipeline
        self._config = config

    def diarize(self, audio_path: Path, progress_cb: ProgressFn) -> list[Turn]:
        if self._torch is None or self._pipeline_class is None:
            raise RuntimeError("PyannoteEngine.load() debe ejecutarse antes de diarize()")

        torch = self._torch
        want = self._config.get("device", "auto")
        available = torch.cuda.is_available()
        if want == "auto":
            device = "cuda" if available else "cpu"
        elif want == "cuda" and not available:
            progress_cb("diarization", 0.0, "Se pidió GPU pero torch no tiene CUDA: usando CPU")
            device = "cpu"
        else:
            device = want
        progress_cb("diarization", 0.0, f"Cargando pyannote en {device.upper()}…")

        def run(device_name: str) -> list[Turn]:
            pipeline = self._pipeline_class(token=self._config.get("hf_token") or None, device=device_name)

            def on_progress(pct: float) -> None:
                fraction = min(1.0, max(0.0, pct / 100.0))
                progress_cb("diarization", fraction, f"Diarizando ({pct:.0f} %)")

            kwargs = {}
            if self._config.get("min_speakers"):
                kwargs["min_speakers"] = self._config["min_speakers"]
            if self._config.get("max_speakers"):
                kwargs["max_speakers"] = self._config["max_speakers"]
            annotation = pipeline(str(audio_path), progress_callback=on_progress, **kwargs)
            return [
                Turn(start=float(row["start"]), end=float(row["end"]), speaker=str(row["speaker"]))
                for _, row in annotation.iterrows()
            ]

        try:
            return run(device)
        except (torch.cuda.OutOfMemoryError, RuntimeError, AssertionError) as exc:
            if device != "cpu" and _is_gpu_error(exc):
                progress_cb("diarization", 0.0, f"GPU sin memoria ({exc}): reintentando en CPU…")
                return run("cpu")
            raise

    def unload(self) -> None:
        self._pipeline_class = None
        self._torch = None

    def info(self) -> EngineInfo:
        return EngineInfo(id="pyannote", name="pyannote", description="Diarización de hablantes con pyannote")
