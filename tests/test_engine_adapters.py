import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services.audio.ports import Turn, Word
from app.services.engines.speaker_assignment import assign_word_speakers


def test_pyannote_retries_on_cpu_after_gpu_oom(monkeypatch, tmp_path):
    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(
        is_available=lambda: True,
        OutOfMemoryError=type("OutOfMemoryError", (RuntimeError,), {}),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    fake_whisperx = ModuleType("whisperx")
    fake_whisperx.__path__ = []
    fake_diarize = ModuleType("whisperx.diarize")
    attempts = []

    class FakeAnnotation:
        def iterrows(self):
            return iter([(0, {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"})])

    class FakePipeline:
        def __init__(self, token, device):
            self.device = device

        def __call__(self, audio_path, progress_callback, **kwargs):
            attempts.append(self.device)
            if self.device == "cuda":
                raise fake_torch.cuda.OutOfMemoryError("CUDA out of memory")
            progress_callback(60)
            return FakeAnnotation()

    fake_diarize.DiarizationPipeline = FakePipeline
    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)
    monkeypatch.setitem(sys.modules, "whisperx.diarize", fake_diarize)

    from app.services.engines.diar.pyannote import PyannoteEngine

    engine = PyannoteEngine()
    engine.load({"device": "auto", "hf_token": "synthetic-token"})
    progress = []

    turns = engine.diarize(tmp_path / "synthetic.wav", lambda stage, fraction, detail: progress.append((stage, fraction, detail)))

    assert attempts == ["cuda", "cpu"]
    assert turns == [Turn(start=0.0, end=1.0, speaker="SPEAKER_00")]
    assert any("reintentando en CPU" in detail for _, _, detail in progress)
    assert any(fraction == 0.6 for _, fraction, _ in progress)


@pytest.mark.parametrize(
    "config, message",
    [
        ({"model": "", "device": "cpu", "compute_type": "int8", "batch_size": 8, "chunk_minutes": 5, "language": "es"}, "modelo"),
        ({"model": "small", "device": "auto", "compute_type": "int8", "batch_size": 8, "chunk_minutes": 5, "language": "es"}, "device"),
    ],
)
def test_whisperx_rejects_invalid_options_before_importing_engine(config, message):
    from app.services.engines.asr.whisperx import WhisperXEngine

    with pytest.raises(ValueError, match=message):
        WhisperXEngine().load(config)


def test_assign_word_speakers_returns_original_words_when_assignment_fails():
    words = [Word(word="hola", start=0.0, end=0.4, speaker=None)]
    turns = [Turn(start=None, end=1.0, speaker="SPEAKER_00")]

    result = assign_word_speakers(words, turns)

    assert result == words
    assert result[0] is not words[0]
    assert words[0].speaker is None


def test_importing_adapters_does_not_import_whisperx_or_torch(monkeypatch):
    module_names = (
        "app.services.engines.asr.whisperx",
        "app.services.engines.diar.pyannote",
        "app.services.engines.diar.none",
        "app.services.engines.speaker_assignment",
    )
    for name in module_names:
        sys.modules.pop(name, None)
    for name in ("torch", "whisperx", "whisperx.diarize"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    assert "whisperx" not in sys.modules
    assert "torch" not in sys.modules
    for name in module_names:
        importlib.import_module(name)
        assert "whisperx" not in sys.modules
        assert "torch" not in sys.modules
