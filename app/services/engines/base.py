from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..audio.ports import AsrResult, EngineInfo, ProgressFn, Turn


class Engine(Protocol):
    def load(self, config: dict[str, Any]) -> None: ...

    def unload(self) -> None: ...

    def info(self) -> EngineInfo: ...


class ASREngine(Engine, Protocol):
    def transcribe(self, audio: Any) -> AsrResult: ...


class DiarizationEngine(Engine, Protocol):
    def diarize(self, audio_path: Path, progress_cb: ProgressFn) -> list[Turn]: ...
