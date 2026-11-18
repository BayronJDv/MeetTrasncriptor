import json

from app import config
from app.routers import settings
from app.schemas import SettingsPatch


def test_load_config_migrates_v1_and_preserves_values(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    legacy = {
        "asr": {"model": "base"},
        "llm": {"api_key": "secret-key", "model": "legacy-model"},
        "custom_option": {"enabled": True},
    }
    config_path.write_text(json.dumps(legacy), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "templates")

    migrated = config.load_config()

    assert migrated["schema_version"] == 2
    assert migrated["asr"]["model"] == "base"
    assert migrated["llm"]["api_key"] == "secret-key"
    assert migrated["llm"]["model"] == "legacy-model"
    assert migrated["custom_option"] == {"enabled": True}
    assert set(migrated["llm"]["tasks"]) == {
        "review", "meeting_1", "meeting_2", "report_1", "report_2"
    }


def test_get_settings_masks_secrets(monkeypatch):
    monkeypatch.setattr(
        settings,
        "load_config",
        lambda: {"llm": {"api_key": "secret-key"}, "diar": {"hf_token": "secret-token"}},
    )

    result = settings.get_settings()

    assert result["config"]["llm"]["api_key"] == "********"
    assert result["config"]["diar"]["hf_token"] == "********"


def test_put_settings_preserves_secrets_and_omitted_values(monkeypatch):
    previous = {
        "llm": {"api_key": "secret-key", "temperature": 0.2},
        "diar": {"hf_token": "secret-token"},
    }
    captured = {}
    monkeypatch.setattr(settings, "load_config", lambda: previous)

    def fake_save_config(payload):
        captured.update(payload)
        return {
            **previous,
            "llm": {**previous["llm"], **payload.get("llm", {})},
            "diar": {**previous["diar"], **payload.get("diar", {})},
        }

    monkeypatch.setattr(settings, "save_config", fake_save_config)
    patch = SettingsPatch.model_validate(
        {"llm": {"api_key": "********", "temperature": 0.7}, "diar": {"hf_token": "********"}}
    )

    result = settings.put_settings(patch)

    assert captured["llm"] == {"api_key": "secret-key", "temperature": 0.7}
    assert captured["diar"] == {"hf_token": "secret-token"}
    assert result["config"]["llm"]["api_key"] == "********"
    assert result["config"]["diar"]["hf_token"] == "********"
