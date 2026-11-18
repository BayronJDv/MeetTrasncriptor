from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class AudioBuffer:
    samples: np.ndarray
    sample_rate: int
    duration: float


@dataclass
class Word:
    word: str
    start: float | None
    end: float | None
    speaker: str | None = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    speaker: str | None = None


@dataclass
class Turn:
    start: float
    end: float
    speaker: str


@dataclass
class AsrResult:
    segments: list[Segment]
    language: str | None = None


@dataclass
class EngineInfo:
    id: str
    name: str
    description: str


ProgressFn = Callable[[str, float, str], None]
CancelFn = Callable[[], None]
