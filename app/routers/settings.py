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


@router.get("/settings")
def get_settings() -> dict:
    cfg = load_config()
    # nunca exponer la clave completa al frontend de más: se envía para poder editarla,
    # pero la app corre solo en localhost
    return {"config": cfg, "providers": PROVIDERS}


@router.put("/settings")
def put_settings(patch: SettingsPatch) -> dict:
    payload = {}
    for section in ("asr", "diar", "llm", "report"):
        part = getattr(patch, section)
        if part is not None:
            payload[section] = part.model_dump(exclude_none=False)
    cfg = save_config(payload)
    return {"config": cfg}


@router.get("/system")
def system_info() -> dict:
    import platform

    info: dict = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or "desconocido",
        "ffmpeg": bool(shutil.which("ffmpeg")) or "imageio-ffmpeg",
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info["gpu"] = props.name
            info["gpu_vram_gb"] = round(props.total_memory / 1024**3, 1)
    except Exception as exc:  # noqa: BLE001
        info["torch"] = f"no disponible ({exc})"
        info["cuda_available"] = False

    info["ram_gb"] = _ram_gb()

    # recomendación según hardware (MX150 2GB / 16GB RAM → ASR en CPU int8)
    rec_asr_device = "cpu"
    rec_compute = "int8"
    rec_model = "small"
    rec_diar = "cuda" if info.get("cuda_available") else "cpu"
    info["recommendation"] = {
        "asr_device": rec_asr_device,
        "compute_type": rec_compute,
        "model": rec_model,
        "diar_device": rec_diar,
        "note": (
            "GPU detectada: la diarización puede usar CUDA. "
            if info.get("cuda_available")
            else "Sin torch-CUDA: la diarización usará CPU (más lenta en audios largos). "
            "Para usar la GPU instala torch con CUDA."
        ),
    }
    return info
