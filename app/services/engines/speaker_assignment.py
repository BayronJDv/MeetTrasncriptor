from __future__ import annotations

from dataclasses import replace

from ..audio.ports import Turn, Word


def assign_word_speakers(words: list[Word], turns: list[Turn]) -> list[Word]:
    assigned = [replace(word) for word in words]
    if not turns:
        return assigned

    try:
        for word in assigned:
            if word.start is None or word.end is None:
                continue
            overlaps: dict[str, float] = {}
            for turn in turns:
                start = float(turn.start)
                end = float(turn.end)
                overlap = max(0.0, min(float(word.end), end) - max(float(word.start), start))
                if overlap:
                    overlaps[turn.speaker] = overlaps.get(turn.speaker, 0.0) + overlap
            if overlaps:
                word.speaker = max(overlaps, key=overlaps.get)
    except Exception:
        return [replace(word) for word in words]
    return assigned
