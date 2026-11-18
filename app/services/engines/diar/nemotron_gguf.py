from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ...audio.ports import CancelFn, EngineInfo, ProgressFn, Turn
from ....jobs import JobCancelled


MODEL_ID = "nvidia/Nemotron-3-Diarization"
MODEL_NAME = "Nemotron-3-Diarization"
MAX_SPEAKERS = 8


class NemotronGGUFEngine:
    def __init__(self):
        self._binary: str | None = None
        self._model: Path | None = None
        self.warnings: list[str] = []

    def load(self, config: dict[str, Any], check_cancel: CancelFn | None = None) -> None:
        check_cancel = check_cancel or (lambda: None)
        binary = shutil.which("nemo-speech")
        if binary is None:
            raise RuntimeError("Motor no instalado: no se encontró el binario nemo-speech")

        model_value = config.get("model")
        if not isinstance(model_value, str) or not model_value:
            raise ValueError(f"Nemotron requiere el GGUF local de {MODEL_ID}")
        model = Path(model_value).expanduser()
        if model.suffix.lower() != ".gguf" or not model.is_file():
            raise ValueError(f"Nemotron requiere la ruta local existente de un GGUF de {MODEL_ID}")
        max_speakers = config.get("max_speakers")
        if max_speakers is not None and (not isinstance(max_speakers, int) or max_speakers < 1):
            raise ValueError("Nemotron max_speakers debe ser un entero positivo")

        check_cancel()
        model = model.resolve()
        output = self._run([binary, "model", "info", str(model)], check_cancel)
        try:
            info = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ValueError("nemo-speech model info devolvió JSON inválido") from exc
        if (
            not isinstance(info, dict)
            or info.get("name") != MODEL_NAME
            or info.get("role") != "diarization"
            or info.get("runtime_compatible") is not True
        ):
            raise ValueError(
                f"GGUF inválido: se requiere {MODEL_NAME} compatible con diarización; "
                "Sortformer no está permitido"
            )

        self._binary = binary
        self._model = model
        self.warnings = []
        if max_speakers is not None and max_speakers > MAX_SPEAKERS:
            self._warn("Nemotron admite hasta 8 hablantes; para más, usa pyannote.")
        check_cancel()

    def diarize(
        self,
        audio_path: Path,
        progress_cb: ProgressFn,
        check_cancel: CancelFn | None = None,
    ) -> list[Turn]:
        if self._binary is None or self._model is None:
            raise RuntimeError("NemotronGGUFEngine.load() debe ejecutarse antes de diarize()")
        check_cancel = check_cancel or (lambda: None)
        check_cancel()
        progress_cb("diarization", 0.0, "Diarizando con Nemotron-3…")
        command = [
            self._binary,
            "diarize",
            str(audio_path),
            "--model",
            str(self._model),
            "--format",
            "json",
        ]
        output = self._run(command, check_cancel)
        turns = self._parse_result(output)
        speakers = {turn.speaker for turn in turns}
        if len(speakers) > MAX_SPEAKERS:
            self._warn("Nemotron admite hasta 8 hablantes; para más, usa pyannote.")
        check_cancel()
        progress_cb("diarization", 1.0, "Diarización completada")
        return turns

    def _warn(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)

    @staticmethod
    def _run(command: list[str], check_cancel: CancelFn) -> str:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            while True:
                check_cancel()
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except JobCancelled:
            process.kill()
            process.communicate()
            raise

        if process.returncode != 0:
            detail = (stderr or "").strip()
            raise RuntimeError(f"Falló nemo-speech {command[1]}: {detail or process.returncode}")
        return stdout

    @staticmethod
    def _parse_result(output: str) -> list[Turn]:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ValueError("nemo-speech diarize devolvió JSON inválido") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
            raise ValueError("nemo-speech JSON no contiene la lista de segmentos esperada")

        turns = []
        for item in payload["segments"]:
            if not isinstance(item, dict):
                raise ValueError("nemo-speech devolvió un segmento inválido")
            try:
                start = float(item["start"])
                end = float(item["end"])
                speaker = int(item["speaker"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("nemo-speech devolvió un segmento con tiempos/hablante inválidos") from exc
            if start < 0 or end <= start or speaker < 1:
                raise ValueError("nemo-speech devolvió un segmento con tiempos/hablante inválidos")
            turns.append(Turn(start=start, end=end, speaker=f"speaker_{speaker}"))
        return turns

    def unload(self) -> None:
        self._binary = None
        self._model = None

    def info(self) -> EngineInfo:
        return EngineInfo(
            id="nemotron_gguf",
            name="Nemotron-3-Diarization (GGUF)",
            description="Diarización local con NeMo-Speech.cpp (OpenMDW-1.1; hasta 8 hablantes)",
        )
