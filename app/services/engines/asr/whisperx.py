from __future__ import annotations

from typing import Any, Callable

from ...audio.ports import AsrResult, EngineInfo, Segment, Word

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

    def load(self, config: dict[str, Any]) -> None:
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

    def transcribe(self, audio: Any) -> AsrResult:
        if self._model is None or self._whisperx is None:
            raise RuntimeError("WhisperXEngine.load() debe ejecutarse antes de transcribe()")

        result = self._model.transcribe(
            audio,
            batch_size=self._config["batch_size"],
            language=self._config["language"] or None,
        )
        language = result.get("language") or self._config["language"] or "es"
        if not self._alignment_attempted:
            self._alignment_attempted = True
            try:
                if language not in _alignment_cache:
                    _alignment_cache[language] = self._whisperx.load_align_model(language_code=language, device="cpu")
                self._alignment = _alignment_cache[language]
                self._language = language
                self._log(f"Modelo de alineación cargado (idioma: {language})")
            except Exception as exc:
                self._log(f"Alineación no disponible ({exc}); se usarán tiempos del ASR")

        segments = result["segments"]
        if self._alignment:
            try:
                segments = self._whisperx.align(
                    segments,
                    self._alignment[0],
                    self._alignment[1],
                    audio,
                    "cpu",
                    return_char_alignments=False,
                )["segments"]
            except Exception as exc:
                self._log(f"Alineación fallida: {exc}")
                segments = result["segments"]

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
