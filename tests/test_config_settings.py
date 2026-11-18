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

    assert migrated["schema_version"] == 3
    assert migrated["asr"]["engine"] == "whisperx"
    assert migrated["asr"]["options"]["whisperx"]["model"] == "base"
    assert migrated["asr"]["model"] == "base"
    assert migrated["llm"]["api_key"] == "secret-key"
    assert migrated["llm"]["model"] == "legacy-model"
    assert migrated["custom_option"] == {"enabled": True}
    assert set(migrated["llm"]["tasks"]) == {
        "review", "meeting_1", "meeting_2", "report_1", "report_2"
    }


def test_load_config_migrates_v2_engine_options(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    legacy = {
        "schema_version": 2,
        "asr": {
            "model": "medium",
            "language": "es",
            "device": "cuda",
            "compute_type": "float16",
            "batch_size": 4,
            "chunk_minutes": 7,
        },
        "diar": {
            "device": "cpu",
            "hf_token": "hf-secret",
            "min_speakers": 2,
            "max_speakers": 5,
            "clips_per_speaker": 3,
        },
    }
    config_path.write_text(json.dumps(legacy), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "templates")

    migrated = config.load_config()

    assert migrated["schema_version"] == 3
    assert migrated["asr"]["options"]["whisperx"] == {
        "model": "medium", "device": "cuda", "compute_type": "float16", "batch_size": 4, "chunk_minutes": 7
    }
    assert migrated["diar"]["engine"] == "pyannote"
    assert migrated["diar"]["options"]["pyannote"] == {
        "device": "cpu", "hf_token": "hf-secret", "min_speakers": 2, "max_speakers": 5, "clips_per_speaker": 3
    }
    assert migrated["diar"]["hf_token"] == "hf-secret"


def test_default_engines_preserve_whisperx_and_pyannote():
    assert config.DEFAULT_CONFIG["asr"]["engine"] == "whisperx"
    assert config.DEFAULT_CONFIG["diar"]["engine"] == "pyannote"
    assert config.DEFAULT_CONFIG["asr"]["options"]["whisperx"]["model"] == "small"


def test_advanced_settings_defaults_preserve_existing_limits():
    assert config.DEFAULT_CONFIG["advanced"] == {
        "max_suggestions": 10,
        "report_template_max_chars": 12000,
        "report_meeting_max_chars": 6000,
        "report_instructions_max_chars": 4000,
        "report_notes_max_chars": 120000,
    }


def test_put_settings_persists_advanced_settings(monkeypatch):
    captured = {}
    previous = config.DEFAULT_CONFIG
    monkeypatch.setattr(settings, "load_config", lambda: previous)

    def fake_save_config(payload):
        captured.update(payload)
        return config._deep_merge(previous, payload)

    monkeypatch.setattr(settings, "save_config", fake_save_config)

    settings.put_settings(SettingsPatch.model_validate({"advanced": {"max_suggestions": 5}}))

    assert captured == {"advanced": {"max_suggestions": 5}}


def test_get_settings_masks_secrets(monkeypatch):
    monkeypatch.setattr(
        settings,
        "load_config",
        lambda: {"llm": {"api_key": "secret-key"}, "diar": {"hf_token": "secret-token"}},
    )

    result = settings.get_settings()

    assert result["config"]["llm"]["api_key"] == "********"
    assert result["config"]["diar"]["hf_token"] == "********"
    assert result["config"]["diar"]["options"]["pyannote"]["hf_token"] == "********"


def test_put_settings_preserves_secrets_and_omitted_values(monkeypatch):
    previous = {
        "llm": {"api_key": "secret-key", "temperature": 0.2},
        "diar": {
            "hf_token": "secret-token",
            "options": {"pyannote": {"hf_token": "secret-token", "min_speakers": 2}},
        },
    }
    captured = {}
    monkeypatch.setattr(settings, "load_config", lambda: previous)

    def fake_save_config(payload):
        captured.update(payload)
        return config._deep_merge(previous, payload)

    monkeypatch.setattr(settings, "save_config", fake_save_config)
    patch = SettingsPatch.model_validate(
        {
            "llm": {"api_key": "********", "temperature": 0.7},
            "diar": {
                "hf_token": "********",
                "options": {"pyannote": {"hf_token": "********", "min_speakers": 3}},
            },
        }
    )

    result = settings.put_settings(patch)

    assert captured["llm"] == {"api_key": "secret-key", "temperature": 0.7}
    assert captured["diar"]["hf_token"] == "secret-token"
    assert captured["diar"]["options"]["pyannote"]["hf_token"] == "secret-token"
    assert captured["diar"]["options"]["pyannote"]["min_speakers"] == 3
    assert result["config"]["llm"]["api_key"] == "********"
    assert result["config"]["diar"]["hf_token"] == "********"
    assert result["config"]["diar"]["options"]["pyannote"]["hf_token"] == "********"
