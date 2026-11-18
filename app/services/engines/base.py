from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..audio.ports import AsrResult, CancelFn, EngineInfo, ProgressFn, Turn


class Engine(Protocol):
    def load(self, config: dict[str, Any], check_cancel: CancelFn | None = None) -> None: ...

    def unload(self) -> None: ...

    def info(self) -> EngineInfo: ...


class ASREngine(Engine, Protocol):
    def transcribe(self, audio: Any, check_cancel: CancelFn | None = None) -> AsrResult: ...


class DiarizationEngine(Engine, Protocol):
    def diarize(
        self,
        audio_path: Path,
        progress_cb: ProgressFn,
        check_cancel: CancelFn | None = None,
    ) -> list[Turn]: ...
