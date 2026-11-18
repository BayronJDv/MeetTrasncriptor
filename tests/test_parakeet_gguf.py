import json
import os
import subprocess

import numpy as np
import pytest

from app.config import DEFAULT_CONFIG
from app.jobs import JobCancelled
from app.services import transcription
from app.services.audio.ports import Word
from app.services.engines.asr import parakeet_gguf
from app.services.engines.asr.parakeet_gguf import ParakeetGGUFEngine


@pytest.fixture
def model_path(tmp_path):
    model = tmp_path / "parakeet-tdt-v3.q8_0.gguf"
    model.write_bytes(b"synthetic gguf")
    return model


def test_parakeet_parses_cli_json_word_timestamps(monkeypatch, model_path):
    output = json.dumps(
        {
            "text": " Hola mundo.",
            "languages": ["es"],
            "words": [
                {"word": "Hola", "start": 0.1, "end": 0.5},
                {"word": "mundo.", "start": 0.6, "end": 1.0},
            ],
        }
    )
    monkeypatch.setattr(parakeet_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return output, ""

    monkeypatch.setattr(parakeet_gguf.subprocess, "Popen", lambda command, **kwargs: CompletedProcess())
    engine = ParakeetGGUFEngine()
    engine.load({"model": str(model_path), "language": "es"})

    result = engine.transcribe(np.zeros(16000, dtype=np.float32))

    assert result.language == "es"
    assert result.segments[0].text == " Hola mundo."
    assert result.segments[0].words == [
        Word("Hola", 0.1, 0.5),
        Word("mundo.", 0.6, 1.0),
    ]


def test_parakeet_reports_missing_binary_clearly(monkeypatch, model_path):
    monkeypatch.setattr(parakeet_gguf.shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="Motor no instalado.*nemo-speech"):
        ParakeetGGUFEngine().load({"model": str(model_path)})


def test_parakeet_cancellation_kills_child_process(monkeypatch):
    cancelled = False

    class FakeProcess:
        returncode = None
        killed = False

        def communicate(self, timeout=None):
            nonlocal cancelled
            if timeout is not None:
                cancelled = True
                raise subprocess.TimeoutExpired("nemo-speech", timeout)
            return "", ""

        def kill(self):
            self.killed = True

    process = FakeProcess()
    monkeypatch.setattr(parakeet_gguf.subprocess, "Popen", lambda command, **kwargs: process)

    def check_cancel():
        if cancelled:
            raise JobCancelled()

    with pytest.raises(JobCancelled):
        ParakeetGGUFEngine._run(["/usr/bin/nemo-speech", "transcribe"], check_cancel)

    assert process.killed is True


def test_parakeet_splits_long_audio_using_shared_chunking(monkeypatch, model_path):
    calls = []
    output = json.dumps({"text": "hola", "languages": ["es"], "words": [{"word": "hola", "start": 0.1, "end": 0.8}]})

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return output, ""

    def fake_popen(command, **kwargs):
        calls.append(command)
        return CompletedProcess()

    monkeypatch.setattr(parakeet_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")
    monkeypatch.setattr(parakeet_gguf.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(parakeet_gguf, "compute_chunks", lambda audio, minutes: [(0.0, 60.0), (60.0, 120.0)])
    engine = ParakeetGGUFEngine()
    engine.load({"model": str(model_path), "language": "es", "chunk_minutes": 1})

    result = engine.transcribe(np.zeros(120 * 16000, dtype=np.float32))

    assert len(calls) == 2
    assert len(result.segments) == 2
    assert result.segments[1].start == pytest.approx(60.1)
    assert all(command[1] == "transcribe" for command in calls)
    assert all("--format" in command and command[command.index("--format") + 1] == "json" for command in calls)
    assert all("--model" in command and command[command.index("--model") + 1] == str(model_path) for command in calls)


@pytest.mark.integration
def test_parakeet_real_binary_transcribes_synthetic_audio(monkeypatch):
    binary = os.environ.get("NEMO_SPEECH_BINARY")
    if not binary:
        pytest.skip("define NEMO_SPEECH_BINARY con nemo-speech instalado")
    model = os.environ.get("PARAKEET_GGUF_MODEL")
    if not model:
        pytest.skip("define PARAKEET_GGUF_MODEL con la ruta al GGUF descargado")
    monkeypatch.setattr(parakeet_gguf.shutil, "which", lambda _: binary)

    engine = ParakeetGGUFEngine()
    engine.load({"model": model, "language": "es"})
    result = engine.transcribe(np.zeros(16000, dtype=np.float32))

    assert isinstance(result.segments, list)


def test_parakeet_is_registered_without_changing_default():
    assert transcription.ENGINE_REGISTRY["asr"]["parakeet_gguf"] == (
        ".engines.asr.parakeet_gguf",
        "ParakeetGGUFEngine",
    )
    assert DEFAULT_CONFIG["asr"]["engine"] == "whisperx"
