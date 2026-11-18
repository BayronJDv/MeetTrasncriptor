import pytest

from app import config
from app.services.llm import meeting, prompts, report, review


def test_render_preserves_json_braces_and_substitutes_variables(monkeypatch):
    monkeypatch.setattr(config, "load_config", lambda: {"prompts": {}})

    rendered = prompts.render("meeting_1", win_lo=1, win_hi=2, segments='{"id": 1}')

    assert '{"partes": [{"tipo": "tema|decision|votacion|compromiso|conclusion|otro"' in rendered["user"]
    assert "Transcripción (min 1–2):\n{\"id\": 1}" in rendered["user"]


def test_validate_rejects_missing_required_variable():
    with pytest.raises(ValueError, match="segments"):
        prompts.validate("review_user", "", "{max_suggestions}")


@pytest.mark.parametrize(
    "configured_prompts",
    [{}, {"review_user": {"system": "", "user": ""}}],
)
def test_get_prompt_falls_back_to_default_when_missing_or_empty(monkeypatch, configured_prompts):
    monkeypatch.setattr(config, "load_config", lambda: {"prompts": configured_prompts})

    assert prompts.get_prompt("review_user") == prompts.DEFAULT_PROMPTS["review_user"]


def test_default_user_prompts_match_original_texts():
    assert prompts.DEFAULT_PROMPTS["review_user"]["user"] == review.USER_TEMPLATE
    assert prompts.DEFAULT_PROMPTS["meeting_1"]["user"] == meeting.PHASE1_PROMPT
    assert prompts.DEFAULT_PROMPTS["meeting_2"]["user"] == meeting.PHASE2_PROMPT
    assert prompts.DEFAULT_PROMPTS["report_1"]["user"] == report.PHASE1_PROMPT
    assert prompts.DEFAULT_PROMPTS["report_2"]["user"] == report.PHASE2_PROMPT


def test_default_system_prompts_match_inline_texts():
    assert prompts.DEFAULT_PROMPTS["review_system"]["system"] == review.SYSTEM_PROMPT
    assert prompts.DEFAULT_PROMPTS["meeting_1_system"]["system"] == (
        "Eres un analista experto en actas de reunión. Respondes solo JSON válido en español."
    )
    assert prompts.DEFAULT_PROMPTS["meeting_2_system"]["system"] == (
        "Eres un analista experto en actas de reunión. Respondes solo JSON válido en español."
    )
    assert prompts.DEFAULT_PROMPTS["report_1_system"]["system"] == (
        "Eres un secretário de actas meticuloso. Trabajas en español."
    )
    assert prompts.DEFAULT_PROMPTS["report_2_system"]["system"] == (
        "Eres un redactor profesional de informes y actas de reunión en español. Escribe claro, formal y fiel a los datos."
    )
