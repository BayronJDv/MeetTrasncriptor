import pytest

from app.services.llm import json_utils


@pytest.mark.parametrize(
    "text",
    [
        '```json\n{"ok": true}\n```',
        'Respuesta: {"ok": true} fin de respuesta.',
        '{"items": [1, 2,], "ok": true,}',
    ],
)
def test_extract_json_accepts_common_model_wrappers(text):
    assert json_utils.extract_json(text) == (
        {"items": [1, 2], "ok": True} if "items" in text else {"ok": True}
    )


def test_invalid_json_retries_once_then_raises_actionable_error():
    class FakeClient:
        model = "tiny-model"

        def __init__(self):
            self.messages = []

        def chat_json(self, messages, max_tokens=None):
            self.messages.append(messages)
            raise json_utils.JsonParseError("invalid JSON")

    client = FakeClient()

    with pytest.raises(json_utils.JsonResponseError, match="etapa de prueba.*tiny-model"):
        json_utils.chat_json_with_retry(
            client,
            [{"role": "user", "content": "devuelve JSON"}],
            max_tokens=100,
            stage="etapa de prueba",
            required_key="result",
        )

    assert len(client.messages) == 2
    assert "Responde solo con JSON válido" in client.messages[1][-1]["content"]


def test_chat_json_with_retry_rejects_invalid_required_value_before_retry():
    class FakeClient:
        model = "tiny-model"

        def __init__(self):
            self.responses = iter([{"notes": 123}, {"notes": "notas"}])
            self.calls = 0

        def chat_json(self, messages, max_tokens=None):
            self.calls += 1
            return next(self.responses)

    client = FakeClient()

    result = json_utils.chat_json_with_retry(
        client,
        [{"role": "user", "content": "devuelve JSON"}],
        max_tokens=100,
        stage="notas",
        required_key="notes",
        required_value_type=str,
    )

    assert result == {"notes": "notas"}
    assert client.calls == 2
