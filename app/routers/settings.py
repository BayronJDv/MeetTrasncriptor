"""Ajustes globales + detección de hardware del equipo."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from ..config import load_config, save_config
from ..schemas import SettingsPatch
from ..services.llm.client import PROVIDERS

router = APIRouter(prefix="/api", tags=["settings"])


def _ram_gb() -> float | None:
    if sys.platform == "win32":
        try:
            import ctypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemoryStatus()
            stat.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / 1024**3, 1)
        except (AttributeError, OSError, ValueError):
            return None
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
        except (OSError, ValueError, IndexError):
            return None
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
            )
            return round(int(result.stdout.strip()) / 1024**3, 1)
        except (OSError, subprocess.CalledProcessError, ValueError):
            return None
    return None


def _ram_available_gb() -> float | None:
    if sys.platform == "win32":
        try:
            import ctypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullAvailPhys / 1024**3, 1)
        except (AttributeError, OSError, ValueError):
            return None
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
        except (OSError, ValueError, IndexError):
            return None
    return None


def _mask_secrets(cfg: dict) -> dict:
    cfg = dict(cfg)
    cfg["llm"] = dict(cfg.get("llm", {}))
    cfg["diar"] = dict(cfg.get("diar", {}))
    cfg["llm"]["api_key"] = "********"
    cfg["diar"]["hf_token"] = "********"
    diar_options = dict(cfg["diar"].get("options", {}))
    pyannote = dict(diar_options.get("pyannote", {}))
    pyannote["hf_token"] = "********"
    diar_options["pyannote"] = pyannote
    cfg["diar"]["options"] = diar_options
    return cfg


def _sync_engine_options(payload: dict, previous: dict, section: str, option_name: str, keys: tuple[str, ...]) -> None:
    values = payload.get(section)
    if values is None:
        return
    previous_section = previous.get(section, {})
    engine = values.get("engine", previous_section.get("engine", option_name))
    all_options = dict(previous_section.get("options", {}))
    all_options.update(values.get("options", {}))
    options = dict(all_options.get(engine, {}))
    if engine == option_name:
        for key in keys:
            if key in values:
                options[key] = values[key]
            elif key in options:
                values[key] = options[key]
            elif key in previous_section:
                options[key] = previous_section[key]
                values[key] = options[key]
    all_options[engine] = options
    values["options"] = all_options


def _preserve_diar_token(payload: dict, previous: dict) -> None:
    values = payload.get("diar", {})
    old_values = previous.get("diar", {})
    if values.get("hf_token") == "********":
        values["hf_token"] = old_values.get("hf_token", "")
    options = values.get("options", {})
    pyannote = options.get("pyannote", {})
    if pyannote.get("hf_token") == "********":
        options = dict(options)
        pyannote = dict(pyannote)
        old_token = old_values.get("options", {}).get("pyannote", {}).get("hf_token")
        pyannote["hf_token"] = old_token if old_token is not None else old_values.get("hf_token", "")
        options["pyannote"] = pyannote
        values["options"] = options
    if "hf_token" in values:
        options = dict(values.get("options", {}))
        pyannote = dict(options.get("pyannote", {}))
        pyannote["hf_token"] = values["hf_token"]
        options["pyannote"] = pyannote
        values["options"] = options


def _sync_legacy_diar_token(payload: dict) -> None:
    values = payload.get("diar", {})
    if "hf_token" not in values:
        return
    options = dict(values.get("options", {}))
    pyannote = dict(options.get("pyannote", {}))
    pyannote["hf_token"] = values["hf_token"]
    options["pyannote"] = pyannote
    values["options"] = options


@router.get("/settings")
def get_settings() -> dict:
    return {"config": _mask_secrets(load_config()), "providers": PROVIDERS}


@router.put("/settings")
def put_settings(patch: SettingsPatch) -> dict:
    previous = load_config()
    payload = {}
    for section in ("asr", "diar", "llm", "prompts", "report", "advanced"):
        part = getattr(patch, section)
        if part is not None:
            payload[section] = part.model_dump(exclude_unset=True)
    _sync_engine_options(payload, previous, "asr", "whisperx", ("model", "device", "compute_type", "batch_size", "chunk_minutes"))
    _sync_engine_options(payload, previous, "diar", "pyannote", ("device", "hf_token", "min_speakers", "max_speakers", "clips_per_speaker"))
    for section, key in (("llm", "api_key"), ("diar", "hf_token")):
        values = payload.get(section, {})
        if values.get(key) == "********":
            values[key] = previous[section].get(key, "")
    _preserve_diar_token(payload, previous)
    _sync_legacy_diar_token(payload)
    cfg = save_config(payload)
    return {"config": _mask_secrets(cfg)}


def _gpu_info() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"available": False, "name": None, "vram_gb": None}
    first_gpu = result.stdout.splitlines()[0].split(",", 1) if result.stdout.strip() else []
    if len(first_gpu) != 2:
        return {"available": False, "name": None, "vram_gb": None}
    try:
        memory = round(float(first_gpu[1].strip()) / 1024, 1)
    except ValueError:
        return {"available": False, "name": None, "vram_gb": None}
    return {"available": True, "name": first_gpu[0].strip(), "vram_gb": memory}


def recommendations(hardware: dict, installed: set[str]) -> list[dict]:
    profiles = [
        {
            "profile": "cpu_low_memory",
            "applies": (hardware.get("ram_available_gb") is not None and hardware["ram_available_gb"] <= 2) or not hardware.get("gpu"),
            "engines": ["parakeet_gguf", "nemotron_gguf"],
            "alternative": {"engine": "whisperx", "model": "small", "compute_type": "int8", "reason": "99 idiomas"},
        },
        {
            "profile": "nvidia_gpu",
            "applies": bool(hardware.get("gpu") and hardware.get("vram_gb", 0) >= 6),
            "engines": [engine for engine in ("whisperx", "parakeet_gguf") if engine in installed],
            "available_engines": ["whisperx", "parakeet_gguf"],
        },
        {
            "profile": "pyannote",
            "applies": True,
            "engine": "pyannote",
            "requires": ["hf_token", "hf_terms"],
            "terms_urls": [
                "https://huggingface.co/pyannote/speaker-diarization-3.1",
                "https://huggingface.co/pyannote/segmentation-3.0",
            ],
            "confirmation": "Acepto los términos",
        },
    ]
    return profiles


@router.get("/system")
def system_info() -> dict:
    import platform

    gpu = _gpu_info()
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "os": platform.system(),
        "cpu": platform.processor() or "desconocido",
        "ram_gb": _ram_gb(),
        "ram_available_gb": _ram_available_gb(),
        "vram_gb": gpu["vram_gb"],
        "gpu_vram_gb": gpu["vram_gb"],
        "gpu": gpu["name"],
        "cuda_available": gpu["available"],
        "torch": "instalación opcional; no detectada por el endpoint",
        "ffmpeg": bool(shutil.which("ffmpeg")) or "imageio-ffmpeg",
    }
    from ..services.catalog import get_catalog

    engines = get_catalog()
    installed = {engine["id"] for engine in engines if engine["installed"]}
    info["capabilities"] = {
        "nvidia_gpu": gpu["available"],
        "nemo_speech": shutil.which("nemo-speech") is not None,
        "engines_installed": sorted(installed),
    }
    info["recommendations"] = recommendations(
        {"ram_gb": info["ram_gb"], "gpu": gpu["available"], "vram_gb": info["vram_gb"]},
        installed,
    )
    info["recommendation"] = {
        "asr_device": "cuda" if gpu["available"] else "cpu",
        "compute_type": "float16" if gpu["available"] else "int8",
        "model": "small",
        "diar_device": "cuda" if gpu["available"] else "cpu",
        "note": "Recomendaciones por motor disponibles en recommendations.",
    }
    return info
