import math
import wave
from pathlib import Path

import pytest


@pytest.fixture
def audio_file(tmp_path: Path):
    def create_audio(kind: str = "silence", duration: float = 1.0, sample_rate: int = 16000) -> Path:
        if kind not in {"silence", "tone"}:
            raise ValueError("kind must be 'silence' or 'tone'")
        frame_count = int(duration * sample_rate)
        if kind == "silence":
            frames = [0] * frame_count
        else:
            frames = [int(0.25 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(frame_count)]
        path = tmp_path / f"{kind}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            audio.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in frames))
        return path

    return create_audio
