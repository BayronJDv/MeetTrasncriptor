import asyncio
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.routers import catalog as catalog_router
from app.routers import settings
from app.services import catalog


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    app = FastAPI()
    app.include_router(settings.router)
    app.include_router(catalog_router.router)
    return TestClient(app)


def test_recommendations_include_all_profiles_for_simulated_hardware():
    low_ram = settings.recommendations({"ram_available_gb": 2, "gpu": False}, set())
    assert [profile["profile"] for profile in low_ram] == ["cpu_low_memory", "nvidia_gpu", "pyannote"]
    assert low_ram[0]["applies"] is True
    assert low_ram[0]["engines"] == ["parakeet_gguf", "nemotron_gguf"]
    assert low_ram[0]["alternative"]["model"] == "small"

    nvidia = settings.recommendations({"ram_gb": 16, "gpu": True, "vram_gb": 8}, {"whisperx"})
    assert nvidia[1]["applies"] is True
    assert nvidia[1]["engines"] == ["whisperx"]
    assert nvidia[2]["terms_urls"] == [catalog.PYANNOTE_TERMS_URL, catalog.PYANNOTE_SEGMENTATION_TERMS_URL]


def test_unknown_engine_returns_404_and_gguf_install_is_manual(client):
    response = client.get("/api/catalog")
    assert response.status_code == 200
    engines = response.json()
    assert {engine["id"] for engine in engines} == {
        "whisperx", "pyannote", "parakeet_gguf", "nemotron_gguf", "none"
    }
    assert all({"id", "kind", "label", "license", "requirements", "hardware_tier", "installed", "install_hint"} <= engine.keys() for engine in engines)
    assert client.post("/api/engines/not-an-engine/install").status_code == 404
    assert client.post("/api/engines/parakeet_gguf/install").status_code == 409


def test_pyannote_requires_terms_confirmation_and_hf_token(client, monkeypatch):
    monkeypatch.setattr(catalog, "has_hf_token", lambda: False)
    assert client.post("/api/engines/pyannote/install", json={"terms_confirmation": "Acepto los términos"}).status_code == 400
    monkeypatch.setattr(catalog, "has_hf_token", lambda: True)
    assert client.post("/api/engines/pyannote/install", json={"terms_confirmation": "yes"}).status_code == 400
    monkeypatch.setattr(catalog, "accept_pyannote_terms", lambda: None)
    monkeypatch.setattr(catalog_router.manager, "submit", lambda kind, project_id, fn: type("Job", (), {"snapshot": lambda self: {"kind": kind, "project_id": project_id}})())
    response = client.post("/api/engines/pyannote/install", json={"terms_confirmation": "Acepto los términos"})
    assert response.status_code == 200
    assert response.json()["kind"] == "engine_install"


def test_install_command_uses_only_catalog_extra(monkeypatch):
    calls = []

    class FakeProcess:
        returncode = 0

        def communicate(self, timeout):
            return "", None

        def terminate(self):
            raise AssertionError("unexpected terminate")

        def wait(self):
            return 0

    monkeypatch.setattr(catalog.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)) or FakeProcess())
    catalog.install_extra("whisperx")
    assert calls[0][0] == [sys.executable, "-m", "pip", "install", ".[asr-whisperx]"]
    with pytest.raises(ValueError):
        catalog.install_extra("whisperx; arbitrary-command")
    assert len(calls) == 1


def test_system_and_catalog_do_not_import_heavy_engines(client, monkeypatch):
    heavy_modules = ("torch", "whisperx", "pyannote", "faster_whisper", "nemo", "llama_cpp", "ctranslate2")
    for module in heavy_modules:
        monkeypatch.delitem(sys.modules, module, raising=False)

    response = client.get("/api/system")
    assert response.status_code == 200
    assert "ram_gb" in response.json()
    assert "ram_available_gb" in response.json()
    assert "vram_gb" in response.json()
    assert "recommendations" in response.json()
    assert client.get("/api/catalog").status_code == 200
    assert all(module not in sys.modules for module in heavy_modules)


def test_startup_does_not_initialize_ffmpeg_or_download_models(monkeypatch):
    from app import main

    monkeypatch.setattr(main.config, "ensure_dirs", lambda: None)
    monkeypatch.setattr(main.manager, "start", lambda loop: None)
    monkeypatch.setattr("app.ffmpeg_utils.get_ffmpeg", lambda: pytest.fail("startup must stay empty"))
    asyncio.run(main.startup())
