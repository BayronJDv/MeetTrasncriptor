"""Configuración global persistente (data/config.json) y rutas del proyecto."""
from __future__ import annotations

import copy
import json
import threading
import uuid
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
CONFIG_PATH = DATA_DIR / "config.json"
TEMPLATES_DIR = BASE_DIR / "templates"
BIN_DIR = DATA_DIR / "bin"

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 2,
    "asr": {
        "model": "small",
        "language": "es",
        "device": "cpu",
        "compute_type": "int8",
        "batch_size": 8,
        "chunk_minutes": 5,
    },
    "diar": {
        "device": "auto",
        "hf_token": "",
        "min_speakers": None,
        "max_speakers": None,
        "clips_per_speaker": 4,
    },
    "llm": {
        "provider": "groq",
        "api_key": "",
        "model": "openai/gpt-oss-120b",
        "base_url": "",
        "temperature": 0.2,
        "window_minutes": 10,
        "concurrency": 2,
        "max_retries": 4,
        "tasks": {
            "review": {"model": None, "max_tokens": 2048, "timeout": 180},
            "meeting_1": {"model": None, "max_tokens": 3000, "timeout": 180},
            "meeting_2": {"model": None, "max_tokens": 6000, "timeout": 180},
            "report_1": {"model": None, "max_tokens": 3500, "timeout": 180},
            "report_2": {"model": None, "max_tokens": 8000, "timeout": 180},
        },
    },
    "prompts": {
        "review_system": {"system": "", "user": ""},
        "review_user": {"system": "", "user": ""},
        "meeting_1_system": {"system": "", "user": ""},
        "meeting_1": {"system": "", "user": ""},
        "meeting_2_system": {"system": "", "user": ""},
        "meeting_2": {"system": "", "user": ""},
        "report_1_system": {"system": "", "user": ""},
        "report_1": {"system": "", "user": ""},
        "report_2_system": {"system": "", "user": ""},
        "report_2": {"system": "", "user": ""},
    },
    "report": {
        "export_format": "docx",
    },
    "advanced": {
        "max_suggestions": 10,
        "report_template_max_chars": 12000,
        "report_meeting_max_chars": 6000,
        "report_instructions_max_chars": 4000,
        "report_notes_max_chars": 120000,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
    },
}

_lock = threading.Lock()


def ensure_dirs() -> None:
    for d in (DATA_DIR, PROJECTS_DIR, TEMPLATES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _migrate_v1(cfg: dict) -> dict:
    if cfg.get("schema_version", 1) >= 2:
        return cfg
    migrated = _deep_merge(DEFAULT_CONFIG, cfg)
    migrated["schema_version"] = 2
    return migrated


def load_config() -> dict:
    ensure_dirs()
    with _lock:
        if CONFIG_PATH.exists():
            try:
                stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError) as exc:
                backup = CONFIG_PATH.with_name("config.json.corrupto")
                try:
                    CONFIG_PATH.replace(backup)
                except OSError:
                    pass
                print(
                    f"AVISO: data/config.json ilegible ({exc}). "
                    f"Se movió a {backup.name}; se usan valores por defecto."
                )
                stored = {}
            merged = _deep_merge(DEFAULT_CONFIG, stored)
            merged["schema_version"] = stored.get("schema_version", 1)
            return _migrate_v1(merged)
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(patch: dict) -> dict:
    ensure_dirs()
    with _lock:
        current: dict = {}
        if CONFIG_PATH.exists():
            try:
                current = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                current = {}
        merged = _deep_merge(_deep_merge(DEFAULT_CONFIG, current), patch)
        CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def update_config_section(section: str, values: dict) -> dict:
    return save_config({section: values})


# ---------- proyectos ----------

def new_project_id() -> str:
    return uuid.uuid4().hex[:12]


def project_dir(project_id: str) -> Path:
    d = PROJECTS_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_projects() -> list[dict]:
    ensure_dirs()
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        meta_path = d / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                projects.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
    return projects


def load_meta(project_id: str) -> dict | None:
    meta_path = PROJECTS_DIR / project_id / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_meta(project_id: str, patch: dict) -> dict:
    meta = load_meta(project_id) or {}
    meta.update(patch)
    (PROJECTS_DIR / project_id / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def load_json(project_id: str, name: str) -> Any:
    path = PROJECTS_DIR / project_id / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_json(project_id: str, name: str, data: Any) -> None:
    path = project_dir(project_id) / name
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
