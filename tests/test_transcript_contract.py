import json
from pathlib import Path

import pytest


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "transcript_example.json"


def assert_type(value: object, expected_type: type | tuple[type, ...], path: str) -> None:
    expected_name = expected_type.__name__ if isinstance(expected_type, type) else " or ".join(item.__name__ for item in expected_type)
    assert isinstance(value, expected_type), f"{path} must be {expected_name}, got {type(value).__name__}"


def validate_transcript(transcript: dict) -> None:
    assert_type(transcript, dict, "transcript")
    for key, expected_type in {
        "language": str,
        "duration": (int, float),
        "model": dict,
        "created_at": str,
        "speakers": list,
        "segments": list,
    }.items():
        assert key in transcript, f"transcript missing required key: {key}"
        assert_type(transcript[key], expected_type, f"transcript.{key}")

    model = transcript["model"]
    for key, expected_type in {
        "whisper_model": str,
        "device": str,
        "compute_type": str,
        "diarized": bool,
    }.items():
        assert key in model, f"transcript.model missing required key: {key}"
        assert_type(model[key], expected_type, f"transcript.model.{key}")

    for key in ("engine", "model"):
        if key in model:
            assert_type(model[key], str, f"transcript.model.{key}")

    for index, speaker in enumerate(transcript["speakers"]):
        assert_type(speaker, dict, f"transcript.speakers[{index}]")
        for key, expected_type in {"id": str, "name": (str, type(None)), "clips": list}.items():
            assert key in speaker, f"transcript.speakers[{index}] missing required key: {key}"
            assert_type(speaker[key], expected_type, f"transcript.speakers[{index}].{key}")

    for index, segment in enumerate(transcript["segments"]):
        assert_type(segment, dict, f"transcript.segments[{index}]")
        for key, expected_type in {
            "id": int,
            "start": (int, float),
            "end": (int, float),
            "speaker": (str, type(None)),
            "text": str,
            "words": list,
            "edited": bool,
            "original_text": (str, type(None)),
        }.items():
            assert key in segment, f"transcript.segments[{index}] missing required key: {key}"
            assert_type(segment[key], expected_type, f"transcript.segments[{index}].{key}")

        for word_index, word in enumerate(segment["words"]):
            assert_type(word, dict, f"transcript.segments[{index}].words[{word_index}]")
            for key, expected_type in {
                "word": str,
                "start": (int, float, type(None)),
                "end": (int, float, type(None)),
                "speaker": (str, type(None)),
            }.items():
                assert key in word, f"transcript.segments[{index}].words[{word_index}] missing required key: {key}"
                assert_type(word[key], expected_type, f"transcript.segments[{index}].words[{word_index}].{key}")


def test_transcript_example_matches_contract():
    transcript = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    validate_transcript(transcript)


def test_existing_transcripts_match_contract():
    for transcript_path in sorted(Path("data/projects").glob("*/transcript.json")):
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        validate_transcript(transcript)
