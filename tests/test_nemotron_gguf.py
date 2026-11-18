import json
import subprocess

import pytest

from app.jobs import JobCancelled
from app.services.audio.ports import Turn
from app.services.engines.diar import nemotron_gguf
from app.services.engines.diar.nemotron_gguf import NemotronGGUFEngine


MODEL_INFO = json.dumps(
    {
        "name": "Nemotron-3-Diarization",
        "role": "diarization",
        "runtime_compatible": True,
    }
)


@pytest.fixture
def model_path(tmp_path):
    model = tmp_path / "Nemotron-3-Diarization.q8_0.gguf"
    model.write_bytes(b"synthetic gguf")
    return model


def test_nemotron_parses_segments_to_turns(monkeypatch, model_path, tmp_path):
    audio_path = tmp_path / "meeting.wav"
    audio_path.write_bytes(b"synthetic wav")
    calls = []

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            if calls[-1][1] == "model":
                return MODEL_INFO, ""
            return json.dumps(
                {"file": str(audio_path), "segments": [{"start": 0.2, "end": 1.1, "speaker": 1}]}
            ), ""

    def fake_popen(command, **kwargs):
        calls.append(command)
        return CompletedProcess()

    monkeypatch.setattr(nemotron_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")
    monkeypatch.setattr(nemotron_gguf.subprocess, "Popen", fake_popen)
    engine = NemotronGGUFEngine()
    engine.load({"model": str(model_path)})

    turns = engine.diarize(audio_path, lambda *_: None)

    assert turns == [Turn(start=0.2, end=1.1, speaker="speaker_1")]
    assert calls[0][1:] == ["model", "info", str(model_path)]
    assert calls[1][1:] == [
        "diarize",
        str(audio_path),
        "--model",
        str(model_path),
        "--format",
        "json",
    ]


def test_nemotron_rejects_sortformer_metadata(monkeypatch, model_path):
    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return json.dumps(
                {"name": "diar_streaming_sortformer_4spk-v2", "role": "diarization", "runtime_compatible": True}
            ), ""

    monkeypatch.setattr(nemotron_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")
    monkeypatch.setattr(nemotron_gguf.subprocess, "Popen", lambda command, **kwargs: CompletedProcess())

    with pytest.raises(ValueError, match="Sortformer no está permitido"):
        NemotronGGUFEngine().load({"model": str(model_path)})


def test_nemotron_reports_missing_binary_clearly(monkeypatch, model_path):
    monkeypatch.setattr(nemotron_gguf.shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="Motor no instalado.*nemo-speech"):
        NemotronGGUFEngine().load({"model": str(model_path)})


def test_nemotron_warns_when_more_than_eight_speakers_are_expected(monkeypatch, model_path):
    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return MODEL_INFO, ""

    monkeypatch.setattr(nemotron_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")
    monkeypatch.setattr(nemotron_gguf.subprocess, "Popen", lambda command, **kwargs: CompletedProcess())
    engine = NemotronGGUFEngine()
    engine.load({"model": str(model_path), "max_speakers": 9})

    assert engine.warnings == ["Nemotron admite hasta 8 hablantes; para más, usa pyannote."]


def test_nemotron_warns_when_result_has_more_than_eight_speakers(monkeypatch, model_path, tmp_path):
    audio_path = tmp_path / "meeting.wav"
    audio_path.write_bytes(b"synthetic wav")
    state = {"command": []}

    class CompletedProcess:
        returncode = 0

        def communicate(self, timeout=None):
            if state["command"][1] == "model":
                return MODEL_INFO, ""
            segments = [
                {"start": float(i), "end": float(i + 0.5), "speaker": i}
                for i in range(1, 10)
            ]
            return json.dumps({"segments": segments}), ""

    def fake_popen(command, **kwargs):
        state["command"] = command
        return CompletedProcess()

    monkeypatch.setattr(nemotron_gguf.shutil, "which", lambda _: "/usr/bin/nemo-speech")
    monkeypatch.setattr(nemotron_gguf.subprocess, "Popen", fake_popen)
    engine = NemotronGGUFEngine()
    engine.load({"model": str(model_path)})

    turns = engine.diarize(audio_path, lambda *_: None)

    assert len(turns) == 9
    assert engine.warnings == ["Nemotron admite hasta 8 hablantes; para más, usa pyannote."]


def test_nemotron_cancellation_kills_child_process(monkeypatch):
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
    monkeypatch.setattr(nemotron_gguf.subprocess, "Popen", lambda command, **kwargs: process)

    def check_cancel():
        if cancelled:
            raise JobCancelled()

    with pytest.raises(JobCancelled):
        NemotronGGUFEngine._run(["/usr/bin/nemo-speech", "diarize"], check_cancel)

    assert process.killed is True


def test_nemotron_is_registered_as_optional_engine():
    from app.config import DEFAULT_CONFIG
    from app.services import transcription

    assert transcription.ENGINE_REGISTRY["diar"]["nemotron_gguf"] == (
        ".engines.diar.nemotron_gguf",
        "NemotronGGUFEngine",
    )
    assert DEFAULT_CONFIG["diar"]["engine"] == "pyannote"
