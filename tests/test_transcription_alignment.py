from __future__ import annotations

import sys
from types import ModuleType

import pytest

from app.jobs import JobCancelled
from app.services.engines.asr.whisperx import WhisperXEngine


@pytest.mark.parametrize("cancel_check", [4, 5])
def test_whisperx_cancellation_is_checked_around_alignment(monkeypatch, cancel_check):
    aligned = []
    fake_whisperx = ModuleType("whisperx")
    fake_whisperx.load_align_model = lambda **kwargs: (object(), object())

    def align(*args, **kwargs):
        aligned.append(True)
        return {"segments": args[0]}

    fake_whisperx.align = align
    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            return {
                "language": "es",
                "segments": [{"start": 0.0, "end": 0.5, "text": "hola", "words": []}],
            }

    engine = WhisperXEngine()
    engine._whisperx = fake_whisperx
    engine._model = FakeModel()
    engine._config = {"batch_size": 1, "language": "es"}
    checks = 0

    def cancel_at_alignment_boundary():
        nonlocal checks
        checks += 1
        if checks == cancel_check:
            raise JobCancelled()

    with pytest.raises(JobCancelled):
        engine.transcribe([], check_cancel=cancel_at_alignment_boundary)

    assert aligned == ([] if cancel_check == 4 else [True])
