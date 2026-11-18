from __future__ import annotations

from pathlib import Path
from typing import Any

from ...audio.ports import CancelFn, EngineInfo, ProgressFn, Turn


class NoDiarizationEngine:
    def load(self, config: dict[str, Any] | None = None, check_cancel: CancelFn | None = None) -> None:
        if check_cancel:
            check_cancel()

    def diarize(
        self,
        audio_path: Path,
        progress_cb: ProgressFn | None = None,
        check_cancel: CancelFn | None = None,
    ) -> list[Turn]:
        if check_cancel:
            check_cancel()
        return []

    def unload(self) -> None:
        return None

    def info(self) -> EngineInfo:
        return EngineInfo(id="none", name="Sin diarización", description="No asigna hablantes")
