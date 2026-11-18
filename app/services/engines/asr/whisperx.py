from __future__ import annotations

from typing import Any, Callable

from ...audio.ports import AsrResult, CancelFn, EngineInfo, Segment, Word
from ....jobs import JobCancelled

_model_cache: dict[tuple, Any] = {}
_alignment_cache: dict[str, tuple[Any, Any]] = {}


class WhisperXEngine:
    def __init__(self, log: Callable[[str], None] | None = None):
        self._log = log or (lambda _: None)
        self._whisperx = None
        self._model = None
        self._config: dict[str, Any] = {}
        self._alignment: tuple[Any, Any] | None = None
        self._alignment_attempted = False
        self._language: str | None = None

    def load(self, config: dict[str, Any], check_cancel: CancelFn | None = None) -> None:
        check_cancel = check_cancel or (lambda: None)
        if not isinstance(config.get("model"), str) or not config["model"]:
            raise ValueError("WhisperX requiere un modelo no vacío")
        if config.get("device") not in {"cpu", "cuda"}:
            raise ValueError("WhisperX device debe ser cpu o cuda")
        if config.get("compute_type") not in {"int8", "float16", "float32"}:
            raise ValueError("WhisperX compute_type no es válido")
        if not isinstance(config.get("batch_size"), int) or not 1 <= config["batch_size"] <= 64:
            raise ValueError("WhisperX batch_size debe estar entre 1 y 64")
        if not isinstance(config.get("chunk_minutes"), int) or not 1 <= config["chunk_minutes"] <= 30:
            raise ValueError("WhisperX chunk_minutes debe estar entre 1 y 30")
        if not isinstance(config.get("language"), str):
            raise ValueError("WhisperX language debe ser texto")
        check_cancel()
        import whisperx

        self._whisperx = whisperx
        self._config = config
        key = ("asr", config["model"], config["device"], config["compute_type"])
        if key not in _model_cache:
            _model_cache[key] = whisperx.load_model(
                config["model"],
                config["device"],
                compute_type=config["compute_type"],
                language=config["language"] or None,
            )
        self._model = _model_cache[key]
        check_cancel()

    def transcribe(self, audio: Any, check_cancel: CancelFn | None = None) -> AsrResult:
        if self._model is None or self._whisperx is None:
            raise RuntimeError("WhisperXEngine.load() debe ejecutarse antes de transcribe()")
        check_cancel = check_cancel or (lambda: None)
        check_cancel()
        result = self._model.transcribe(
            audio,
            batch_size=self._config["batch_size"],
            language=self._config["language"] or None,
        )
        language = result.get("language") or self._config["language"] or "es"
        self._language = language
        if not self._alignment_attempted:
            self._alignment_attempted = True
            check_cancel()
            try:
                if language not in _alignment_cache:
                    _alignment_cache[language] = self._whisperx.load_align_model(language_code=language, device="cpu")
                self._alignment = _alignment_cache[language]
                self._language = language
                self._log(f"Modelo de alineación cargado (idioma: {language})")
            except JobCancelled:
                raise
            except Exception as exc:
                self._log(f"Alineación no disponible ({exc}); se usarán tiempos del ASR")
            check_cancel()

        segments = result["segments"]
        if self._alignment:
            check_cancel()
            try:
                segments = self._whisperx.align(
                    segments,
                    self._alignment[0],
                    self._alignment[1],
                    audio,
                    "cpu",
                    return_char_alignments=False,
                )["segments"]
            except JobCancelled:
                raise
            except Exception as exc:
                self._log(f"Alineación fallida: {exc}")
                segments = result["segments"]
            check_cancel()

        converted = []
        for segment in segments:
            text = segment.get("text", "")
            if not text.strip():
                continue
            words = [
                Word(
                    word=word.get("word", ""),
                    start=float(word["start"]) if word.get("start") is not None else None,
                    end=float(word["end"]) if word.get("end") is not None else None,
                    speaker=word.get("speaker"),
                )
                for word in (segment.get("words") or [])
            ]
            converted.append(
                Segment(
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                    text=text,
                    words=words,
                    speaker=segment.get("speaker"),
                )
            )
        return AsrResult(segments=converted, language=self._language or self._config["language"] or "es")

    def unload(self) -> None:
        self._model = None
        self._whisperx = None
        self._alignment = None
        self._alignment_attempted = False
        self._language = None

    def info(self) -> EngineInfo:
        return EngineInfo(id="whisperx", name="WhisperX", description="Transcripción y alineación con WhisperX")
