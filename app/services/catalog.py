from __future__ import annotations

import copy
import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .. import config

PYANNOTE_TERMS_URL = "https://huggingface.co/pyannote/speaker-diarization-3.1"
PYANNOTE_SEGMENTATION_TERMS_URL = "https://huggingface.co/pyannote/segmentation-3.0"
INSTALL_EXTRAS = {
    "whisperx": "asr-whisperx",
    "pyannote": "diar-pyannote",
}

ENGINES = [
    {
        "id": "whisperx",
        "kind": "asr",
        "label": "WhisperX",
        "license": "BSD-2-Clause",
        "requirements": [
            {"type": "ram_gb", "value": 4},
            {"type": "vram_gb", "value": 6},
            {"type": "pip_extra", "value": "asr-whisperx"},
        ],
        "hardware_tier": "gpu_recommended",
        "install_hint": "Instala el extra Python asr-whisperx.",
        "packages": ("whisperx", "torch"),
    },
    {
        "id": "pyannote",
        "kind": "diarization",
        "label": "pyannote",
        "license": "MIT",
        "attribution": "pyannote — speaker-diarization-3.1",
        "requirements": [
            {"type": "hf_token"},
            {"type": "hf_terms", "url": PYANNOTE_TERMS_URL},
            {"type": "hf_terms", "url": PYANNOTE_SEGMENTATION_TERMS_URL},
            {"type": "pip_extra", "value": "diar-pyannote"},
        ],
        "hardware_tier": "cpu_or_gpu",
        "install_hint": "Acepta los términos del modelo y configura tu token HF antes de instalar.",
        "packages": ("whisperx", "pyannote.audio", "torch"),
    },
    {
        "id": "parakeet_gguf",
        "kind": "asr",
        "label": "Parakeet GGUF",
        "license": "CC-BY-4.0",
        "attribution": "NVIDIA NeMo — Parakeet TDT v3",
        "requirements": [
            {"type": "ram_gb", "value": 2},
            {"type": "binary", "value": "nemo-speech (instalación manual)"},
        ],
        "hardware_tier": "cpu_or_gpu",
        "install_hint": "Instala NeMo-Speech.cpp y el modelo GGUF manualmente.",
    },
    {
        "id": "nemotron_gguf",
        "kind": "diarization",
        "label": "Nemotron GGUF",
        "license": "OpenMDW-1.1",
        "attribution": "NVIDIA — Nemotron-3-Diarization",
        "requirements": [
            {"type": "ram_gb", "value": 2},
            {"type": "binary", "value": "nemo-speech (instalación manual)"},
        ],
        "hardware_tier": "cpu_or_gpu",
        "install_hint": "Instala NeMo-Speech.cpp y Nemotron-3-Diarization GGUF manualmente.",
    },
    {
        "id": "none",
        "kind": "diarization",
        "label": "Sin diarización",
        "license": "N/A",
        "requirements": [],
        "hardware_tier": "any",
        "install_hint": "No requiere instalación.",
    },
]


def _is_installed(engine: dict, cfg: dict) -> bool:
    engine_id = engine["id"]
    if engine_id == "none":
        return True
    if engine_id in INSTALL_EXTRAS:
        try:
            for package in engine["packages"]:
                importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return False
        if engine_id == "pyannote":
            options = cfg.get("diar", {}).get("options", {}).get("pyannote", {})
            token = options.get("hf_token") or cfg.get("diar", {}).get("hf_token")
            return bool(token and options.get("terms_accepted"))
        return True
    if shutil.which("nemo-speech") is None:
        return False
    section = "asr" if engine_id == "parakeet_gguf" else "diar"
    options = config.load_config().get(section, {}).get("options", {}).get(engine_id, {})
    model = options.get("model")
    return bool(model and Path(model).expanduser().is_file())


def get_catalog() -> list[dict]:
    cfg = config.load_config()
    result = copy.deepcopy(ENGINES)
    for engine in result:
        engine["installed"] = _is_installed(engine, cfg)
        engine.pop("packages", None)
    return result


def get_engine(engine_id: str) -> dict | None:
    return next((engine for engine in ENGINES if engine["id"] == engine_id), None)


def has_hf_token() -> bool:
    diar = config.load_config().get("diar", {})
    token = diar.get("options", {}).get("pyannote", {}).get("hf_token") or diar.get("hf_token")
    return bool(token)


def accept_pyannote_terms() -> None:
    config.save_config({"diar": {"options": {"pyannote": {"terms_accepted": True}}}})


def install_extra(
    engine_id: str,
    python: str = sys.executable,
    check_cancel: Callable[[], None] = lambda: None,
) -> None:
    extra = INSTALL_EXTRAS.get(engine_id)
    if extra is None:
        raise ValueError("Este motor no tiene instalación Python automática")
    command = [python, "-m", "pip", "install", f".[{extra}]"]
    process = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parents[2],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        while True:
            check_cancel()
            try:
                process.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        process.terminate()
        process.wait()
        raise
    if process.returncode:
        raise RuntimeError(f"Falló la instalación del extra {extra} (código {process.returncode})")
