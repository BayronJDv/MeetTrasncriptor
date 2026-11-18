from __future__ import annotations

from pathlib import Path
from typing import Any

from ...audio.ports import EngineInfo, ProgressFn, Turn


class NoDiarizationEngine:
    def load(self, config: dict[str, Any] | None = None) -> None:
        return None

    def diarize(self, audio_path: Path, progress_cb: ProgressFn | None = None) -> list[Turn]:
        return []

    def unload(self) -> None:
        return None

    def info(self) -> EngineInfo:
        return EngineInfo(id="none", name="Sin diarización", description="No asigna hablantes")
