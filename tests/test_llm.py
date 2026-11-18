import httpx
import pytest

from app import config
from app.routers import llm
from app.services.llm import client, prompts


class FakeResponse:
    status_code = 200
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "OK"}}]}


def test_task_overrides_win_over_global_config(monkeypatch):
    monkeypatch.setattr(
        config,
        "load_config",
        lambda: {
            "llm": {
                "provider": "ollama",
                "model": "global-model",
                "max_tokens": 700,
                "timeout": 30,
                "tasks": {
                    "review": {"model": "task-model", "max_tokens": 1200, "timeout": 90}
                },
            }
        },
    )
    captured = {}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json, headers):
            captured["body"] = json
            return FakeResponse()

    monkeypatch.setattr(client.httpx, "Client", FakeClient)
    llm_client = client.LlmClient(overrides="review")

    llm_client.chat([{"role": "user", "content": "test"}])

    assert captured["body"]["model"] == "task-model"
    assert captured["body"]["max_tokens"] == 1200
    assert captured["timeout"] == 90


def test_list_models_parses_ollama_tags_response(monkeypatch):
    monkeypatch.setattr(
        client.httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200,
            json={"models": [{"name": "llama3.1:latest"}, {"name": "qwen2.5"}]},
            request=httpx.Request("GET", args[0]),
        ),
    )

    assert client.list_models("ollama", "http://localhost:11434/v1", "") == [
        "llama3.1:latest",
        "qwen2.5",
    ]


def test_unknown_provider_raises_llm_error_instead_of_keyerror(monkeypatch):
    monkeypatch.setattr(config, "load_config", lambda: {"llm": {"provider": "unknown"}})

    with pytest.raises(client.LlmError, match="Proveedor LLM desconocido"):
        client.LlmClient()


def test_reset_prompt_restores_default_text(monkeypatch):
    stored = {"review_user": {"system": "custom", "user": "custom"}}
    monkeypatch.setattr(config, "load_config", lambda: {"prompts": stored})
    monkeypatch.setattr(config, "save_config", lambda patch: stored.update(patch["prompts"]) or {})

    result = llm.reset_prompt("review_user")

    assert result["review_user"] == prompts.DEFAULT_PROMPTS["review_user"]
    assert stored["review_user"] == prompts.DEFAULT_PROMPTS["review_user"]


def test_list_models_returns_empty_when_ollama_is_unavailable(monkeypatch):
    def raise_connection_error(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(client.httpx, "get", raise_connection_error)

    assert client.list_models("ollama", "http://localhost:11434/v1", "") == []


def test_put_prompt_persists_after_config_reload(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "templates")
    edited = {"system": "", "user": "PROMPT EDITADO {segments} / {max_suggestions}"}

    llm.put_prompts({"review_user": edited})

    assert config.load_config()["prompts"]["review_user"] == edited
