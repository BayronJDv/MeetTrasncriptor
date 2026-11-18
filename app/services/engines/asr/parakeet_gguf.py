from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ...audio.chunking import SR, compute_chunks
from ...audio.ports import AsrResult, CancelFn, EngineInfo, Segment, Word
from ....jobs import JobCancelled


class ParakeetGGUFEngine:
    def __init__(self, log: Callable[[str], None] | None = None):
        self._log = log or (lambda _: None)
        self._binary: str | None = None
        self._model: Path | None = None
        self._language = "es"
        self._chunk_minutes = 5

    def load(self, config: dict[str, Any], check_cancel: CancelFn | None = None) -> None:
        check_cancel = check_cancel or (lambda: None)
        binary = shutil.which("nemo-speech")
        if binary is None:
            raise RuntimeError("Motor no instalado: no se encontró el binario nemo-speech")

        model_value = config.get("model")
        if not isinstance(model_value, str) or not model_value:
            raise ValueError("Parakeet requiere la ruta local de un modelo GGUF")
        model = Path(model_value).expanduser()
        if model.suffix.lower() != ".gguf" or not model.is_file():
            raise ValueError("Parakeet requiere la ruta local existente de un modelo .gguf")
        chunk_minutes = config.get("chunk_minutes", 5)
        if not isinstance(chunk_minutes, int) or not 1 <= chunk_minutes <= 30:
            raise ValueError("Parakeet chunk_minutes debe estar entre 1 y 30")
        language = config.get("language", "es")
        if not isinstance(language, str):
            raise ValueError("Parakeet language debe ser texto")

        check_cancel()
        self._binary = binary
        self._model = model.resolve()
        self._language = language
        self._chunk_minutes = chunk_minutes
        check_cancel()

    def transcribe(self, audio: Any, check_cancel: CancelFn | None = None) -> AsrResult:
        if self._binary is None or self._model is None:
            raise RuntimeError("ParakeetGGUFEngine.load() debe ejecutarse antes de transcribe()")
        check_cancel = check_cancel or (lambda: None)
        samples = np.asarray(audio, dtype=np.float32)
        chunks = compute_chunks(samples, self._chunk_minutes)
        segments: list[Segment] = []
        detected_language: str | None = None

        for index, (start, end) in enumerate(chunks):
            check_cancel()
            chunk = samples[int(start * SR):int(end * SR)]
            with tempfile.TemporaryDirectory(prefix="meet-transcriptor-parakeet-") as directory:
                audio_path = Path(directory) / "chunk.wav"
                pcm = np.clip(chunk, -1.0, 1.0)
                pcm = (pcm * 32767).astype("<i2")
                with wave.open(str(audio_path), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(SR)
                    wav_file.writeframes(pcm.tobytes())

                command = [
                    self._binary,
                    "transcribe",
                    str(audio_path),
                    "--model",
                    str(self._model),
                    "--format",
                    "json",
                ]
                if self._language:
                    command.extend(("--language", self._language))
                output = self._run(command, check_cancel)

            result = self._parse_result(output, start)
            detected_language = result.language or detected_language
            segments.extend(result.segments)
            self._log(f"Parakeet: tramo {index + 1}/{len(chunks)} transcrito")

        return AsrResult(segments=segments, language=detected_language or self._language or "es")

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
            raise RuntimeError(f"Falló nemo-speech transcribe: {detail or process.returncode}")
        return stdout

    @staticmethod
    def _parse_result(output: str, offset: float = 0.0) -> AsrResult:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ValueError("nemo-speech devolvió JSON inválido") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
            raise ValueError("nemo-speech JSON no contiene la lista de palabras esperada")

        words = []
        for item in payload["words"]:
            if not isinstance(item, dict) or not isinstance(item.get("word"), str):
                raise ValueError("nemo-speech devolvió una palabra inválida")
            try:
                start = float(item["start"]) + offset
                end = float(item["end"]) + offset
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("nemo-speech devolvió timestamps de palabra inválidos") from exc
            words.append(Word(word=item["word"], start=start, end=end))

        text = payload.get("text", "")
        if not isinstance(text, str):
            raise ValueError("nemo-speech devolvió un texto inválido")
        segments = []
        if text.strip():
            start = min((word.start for word in words if word.start is not None), default=offset)
            end = max((word.end for word in words if word.end is not None), default=offset)
            segments.append(Segment(start=start, end=end, text=text, words=words))

        languages = payload.get("languages", [])
        language = languages[0] if isinstance(languages, list) and languages and isinstance(languages[0], str) else None
        return AsrResult(segments=segments, language=language)

    def unload(self) -> None:
        self._binary = None
        self._model = None

    def info(self) -> EngineInfo:
        return EngineInfo(
            id="parakeet_gguf",
            name="Parakeet TDT v3 (GGUF)",
            description="ASR multilingüe local con NeMo-Speech.cpp (CC-BY-4.0)",
        )
