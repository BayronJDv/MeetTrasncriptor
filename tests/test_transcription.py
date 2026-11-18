from __future__ import annotations

import numpy as np
import pytest

from app.jobs import Job, JobCancelled
from app.services.audio.ports import AsrResult, AudioBuffer, EngineInfo, Segment, Turn, Word
from app.services import transcription
from test_transcript_contract import validate_transcript


CFG = {
    "asr": {
        "model": "small",
        "device": "cpu",
        "compute_type": "int8",
        "language": "es",
        "batch_size": 1,
        "chunk_minutes": 1,
    },
    "diar": {"hf_token": ""},
}


class FakeASR:
    def __init__(self, log=None, cancel_stage=None, job=None):
        self.cancel_stage = cancel_stage
        self.job = job
        self.calls = 0

    def load(self, config, check_cancel=None):
        if self.cancel_stage == "load":
            self.job.cancel_event.set()

    def transcribe(self, audio, check_cancel=None):
        self.calls += 1
        if self.cancel_stage == "chunk" and self.calls == 1:
            self.job.cancel_event.set()
        return AsrResult(
            segments=[Segment(0.1, 0.8, "hola", [Word("hola", 0.1, 0.8)])],
            language="es",
        )

    def info(self):
        return EngineInfo("whisperx", "WhisperX", "fake")


class FakeDiar:
    def __init__(self, cancel_stage=None, job=None):
        self.cancel_stage = cancel_stage
        self.job = job

    def load(self, config, check_cancel=None):
        if self.cancel_stage == "diar_load":
            self.job.cancel_event.set()

    def diarize(self, audio_path, progress_cb, check_cancel=None):
        progress_cb("diarization", 0.5, "mitad")
        if self.cancel_stage == "diarize":
            self.job.cancel_event.set()
        return [Turn(0.0, 1.0, "SPEAKER_00")]

    def info(self):
        return EngineInfo("pyannote", "pyannote", "fake")


def test_resolve_engines_instantiates_configured_registry_entries(monkeypatch):
    class RegisteredASR:
        def __init__(self, log=None):
            self.log = log

    class RegisteredDiar:
        pass

    modules = {
        ".engines.asr.whisperx": type("Module", (), {"WhisperXEngine": RegisteredASR}),
        ".engines.diar.none": type("Module", (), {"NoDiarizationEngine": RegisteredDiar}),
    }
    imported = []

    def fake_import(module_name, package):
        imported.append(module_name)
        return modules[module_name]

    monkeypatch.setattr(transcription.importlib, "import_module", fake_import)
    asr, diar = transcription.resolve_engines(
        {"asr": {"engine": "whisperx"}, "diar": {"engine": "none"}}, lambda _: None
    )

    assert isinstance(asr, RegisteredASR)
    assert isinstance(diar, RegisteredDiar)
    assert imported == [".engines.asr.whisperx", ".engines.diar.none"]


def _install_fakes(monkeypatch, tmp_path, job, cancel_stage=None, diarized=False):
    cfg = {"asr": dict(CFG["asr"]), "diar": {"hf_token": "token" if diarized else ""}}
    monkeypatch.setattr(transcription.config, "load_config", lambda: cfg)
    monkeypatch.setattr(
        transcription,
        "resolve_engines",
        lambda config, log: (FakeASR(cancel_stage=cancel_stage, job=job), FakeDiar(cancel_stage, job)),
    )
    samples = np.zeros(32000, dtype=np.float32)
    monkeypatch.setattr(
        transcription,
        "load_audio",
        lambda path: AudioBuffer(samples=samples, sample_rate=16000, duration=2.0),
    )
    monkeypatch.setattr(transcription, "compute_chunks", lambda audio, minutes: [(0.0, 1.0), (1.0, 2.0)])
    if cancel_stage == "decode":
        def decode_and_cancel(path):
            job.cancel_event.set()
            return AudioBuffer(samples=samples, sample_rate=16000, duration=2.0)
        monkeypatch.setattr(transcription, "load_audio", decode_and_cancel)

    updates = []

    def update(fake_job, stage=None, progress=None, detail=None):
        if stage is not None:
            fake_job.stage = stage
        if progress is not None:
            fake_job.progress = max(0.0, min(100.0, progress))
            updates.append(fake_job.progress)
        if detail is not None:
            fake_job.detail = detail

    monkeypatch.setattr(transcription.manager, "update", update)

    saved = {}

    def save_json(project_id, name, data):
        saved[name] = data
        if cancel_stage == "transcript_save":
            job.cancel_event.set()

    def save_meta(project_id, patch):
        saved["meta"] = patch
        if cancel_stage == "meta_save":
            job.cancel_event.set()

    monkeypatch.setattr(transcription.config, "save_json", save_json)
    monkeypatch.setattr(transcription.config, "save_meta", save_meta)
    return updates, saved


def test_transcription_writes_contract_without_diarization(monkeypatch, tmp_path):
    job = Job("job", "project", "transcribe")
    updates, saved = _install_fakes(monkeypatch, tmp_path, job)

    transcription.run("project", tmp_path / "audio.wav", job)

    transcript = saved["transcript.json"]
    validate_transcript(transcript)
    assert transcript["model"]["engine"] == "whisperx"
    assert transcript["model"]["model"] == "small"
    assert transcript["model"]["whisper_model"] == "small"
    assert transcript["model"]["diarized"] is False
    assert transcript["speakers"] == []
    assert [segment["speaker"] for segment in transcript["segments"]] == [None, None]
    assert updates and all(0 <= progress <= 100 for progress in updates)
    assert updates == sorted(updates)
    assert updates[-1] == 98


@pytest.mark.parametrize("stage", ["load", "decode", "chunk", "diar_load", "diarize", "assignment", "transcript_save", "meta_save"])
def test_transcription_cancellation_stops_after_each_long_stage(monkeypatch, tmp_path, stage):
    job = Job("job", "project", "transcribe")
    _install_fakes(monkeypatch, tmp_path, job, cancel_stage=stage, diarized=stage in {"diar_load", "diarize", "assignment"})
    if stage == "assignment":
        def assign_and_cancel(words, turns):
            job.cancel_event.set()
            return words
        monkeypatch.setattr(transcription, "assign_word_speakers", assign_and_cancel)

    with pytest.raises(JobCancelled):
        transcription.run("project", tmp_path / "audio.wav", job)


def test_transcription_with_none_diarization_writes_valid_transcript_without_speakers(monkeypatch, tmp_path):
    job = Job("job", "project", "transcribe")
    _install_fakes(monkeypatch, tmp_path, job)
    cfg = {
        "asr": dict(CFG["asr"], engine="whisperx", options={"whisperx": {}}),
        "diar": {"engine": "none", "options": {"none": {}}},
    }
    monkeypatch.setattr(transcription.config, "load_config", lambda: cfg)

    class NoDiar:
        loaded = False

        def load(self, config, check_cancel=None):
            self.loaded = True

        def diarize(self, audio_path, progress_cb, check_cancel=None):
            raise AssertionError("none no debe ejecutar diarización")

        def info(self):
            return EngineInfo("none", "Sin diarización", "fake")

    no_diar = NoDiar()
    monkeypatch.setattr(transcription, "resolve_engines", lambda config, log: (FakeASR(), no_diar))
    saved = {}
    monkeypatch.setattr(transcription.config, "save_json", lambda project_id, name, data: saved.setdefault(name, data))
    monkeypatch.setattr(transcription.config, "save_meta", lambda project_id, patch: None)

    transcription.run("project", tmp_path / "audio.wav", job)

    transcript = saved["transcript.json"]
    validate_transcript(transcript)
    assert no_diar.loaded is False
    assert transcript["speakers"] == []
    assert all(segment["speaker"] is None for segment in transcript["segments"])
    assert transcript["model"]["diarized"] is False


def test_transcription_assigns_speakers_when_diarization_returns_turns(monkeypatch, tmp_path):
    job = Job("job", "project", "transcribe")
    updates, saved = _install_fakes(monkeypatch, tmp_path, job, diarized=True)

    transcription.run("project", tmp_path / "audio.wav", job)

    transcript = saved["transcript.json"]
    assert transcript["model"]["diarized"] is True
    assert transcript["speakers"] == [{"id": "SPEAKER_00", "name": None, "clips": []}]
    assert transcript["segments"][0]["words"][0]["speaker"] == "SPEAKER_00"
    assert updates and all(0 <= progress <= 100 for progress in updates)
    assert updates == sorted(updates)
    assert 62 in updates and 78 in updates and 95 in updates and updates[-1] == 98
