from __future__ import annotations

from pathlib import Path

import numpy as np

from ...ffmpeg_utils import decode_audio
from .ports import AudioBuffer

SR = 16000


def load_audio(path: Path, sample_rate: int = SR) -> AudioBuffer:
    samples = np.frombuffer(decode_audio(path, sample_rate), dtype=np.float32).copy()
    return AudioBuffer(samples=samples, sample_rate=sample_rate, duration=len(samples) / sample_rate)


def snap_boundary(audio: np.ndarray, target_sec: float, search: float = 3.0, frame_ms: int = 30) -> float:
    """Busca el punto de mínima energía (silencio) cerca de target_sec."""
    frame = int(SR * frame_ms / 1000)
    lo = max(0, int((target_sec - search) * SR))
    hi = min(len(audio), int((target_sec + search) * SR))
    if hi - lo < frame * 3:
        return target_sec
    seg = audio[lo:hi]
    n = len(seg) // frame
    energy = (seg[: n * frame].reshape(n, frame) ** 2).mean(axis=1)
    idx = int(energy.argmin())
    return (lo + idx * frame + frame / 2) / SR


def compute_chunks(audio: np.ndarray, chunk_minutes: int) -> list[tuple[float, float]]:
    total = len(audio) / SR
    win = chunk_minutes * 60
    raw = [x * win for x in range(0, int(total // win) + 1) if x * win > 0]
    raw = [s for s in raw if s < total - 10]
    cuts = [0.0] + [snap_boundary(audio, s) for s in raw] + [total]
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1) if cuts[i + 1] - cuts[i] > 0.5]


def concatenate_audio(paths: list[Path], sample_rate: int = SR) -> AudioBuffer:
    buffers = [load_audio(path, sample_rate).samples for path in paths]
    samples = np.concatenate(buffers) if buffers else np.zeros(0, dtype=np.float32)
    return AudioBuffer(samples=samples, sample_rate=sample_rate, duration=len(samples) / sample_rate)
