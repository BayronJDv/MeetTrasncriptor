"""Utilidades de FFmpeg con el binario de imageio-ffmpeg como alternativa local."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import BIN_DIR

_ffmpeg_path: str | None = None


def get_ffmpeg() -> str:
    """Ruta absoluta a un ejecutable de ffmpeg funcional."""
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path

    # 1) ffmpeg del sistema
    system = shutil.which("ffmpeg")
    if system:
        _ffmpeg_path = system
    else:
        # 2) binario de imageio-ffmpeg, copiado como ffmpeg(.exe) a data/bin
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        local = BIN_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if not local.exists():
            shutil.copy2(bundled, local)
        _ffmpeg_path = str(local)

    # whisperx invoca "ffmpeg" por nombre: prependemos el directorio al PATH
    bin_dir = str(Path(_ffmpeg_path).parent)
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    return _ffmpeg_path


def run_ffmpeg(args: list[str], timeout: int = 3600) -> None:
    """Ejecuta ffmpeg con argumentos (sin el nombre del programa)."""
    cmd = [get_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {proc.stderr.strip()[:500]}")


def decode_audio(source: Path, sample_rate: int = 16000) -> bytes:
    """Decodifica audio mono como muestras PCM float32 a la frecuencia indicada."""
    proc = subprocess.run(
        [
            get_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(sample_rate), "pipe:1",
        ],
        capture_output=True,
        timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {proc.stderr.decode(errors='replace').strip()[:500]}")
    return proc.stdout


def make_playback_copy(source: Path, dest: Path) -> bool:
    """Transcodifica a MP3 mono 96k para reproducción/seek fluido en el navegador.

    Devuelve True si se creó la copia; False si se debe usar el original.
    """
    try:
        run_ffmpeg(["-i", str(source), "-vn", "-ac", "1", "-b:a", "96k", str(dest)])
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def extract_clip(source: Path, start: float, end: float, dest: Path) -> bool:
    """Extrae un fragmento wav 16 kHz mono (carga instantánea en el navegador)."""
    duration = max(0.2, end - start)
    try:
        run_ffmpeg(
            [
                "-ss", f"{max(0.0, start):.3f}",
                "-t", f"{duration:.3f}",
                "-i", str(source),
                "-ar", "16000", "-ac", "1",
                str(dest),
            ]
        )
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def probe_duration(path: Path) -> float:
    """Duración en segundos usando ffprobe (incluido en imageio-ffmpeg)."""
    exe = get_ffmpeg()
    ffprobe = Path(exe).parent / ("ffprobe" + (".exe" if os.name == "nt" else ""))
    if not ffprobe.exists():
        # imageio-ffmpeg no incluye ffprobe: estimar con ffmpeg -i
        cmd = [exe, "-hide_banner", "-i", str(path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        for line in proc.stderr.splitlines():
            if "Duration:" in line:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0
    cmd = [
        str(ffprobe), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0
