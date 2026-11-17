"""Lanzador multiplataforma: prepara el entorno y arranca la aplicación."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DIST_INDEX = WEB_DIR / "dist" / "index.html"
REQUIREMENTS = BASE_DIR / "requirements.txt"
CONFIG_PATH = BASE_DIR / "data" / "config.json"
IS_WINDOWS = os.name == "nt"
MIN_PYTHON = (3, 10)


def venv_dir() -> Path:
    override = os.environ.get("TRANSCRIPTOR_VENV")
    if override:
        return Path(override).expanduser().resolve()
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "transcriptor" / "venv312"
    return BASE_DIR / ".venv"


def venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def python_candidates() -> list[list[str]]:
    if IS_WINDOWS:
        return [["py", "-3.12"], ["py", "-3.11"], ["py", "-3.10"], ["python3.12"], ["python3"], ["python"]]
    return [["python3.12"], ["python3.11"], ["python3.10"], ["python3"], ["python"]]


def python_version(cmd: list[str]) -> tuple[int, int] | None:
    try:
        result = subprocess.run(cmd + ["--version"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    match = re.search(r"(\d+)\.(\d+)", (result.stdout or "") + (result.stderr or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def find_python() -> list[str]:
    for cmd in python_candidates():
        version = python_version(cmd)
        if version and version >= MIN_PYTHON:
            return cmd
    if IS_WINDOWS:
        hint = "winget install Python.Python.3.12"
    elif sys.platform == "darwin":
        hint = "brew install python@3.12"
    else:
        hint = "sudo apt install python3.12 python3.12-venv  (o el equivalente de tu distro)"
    raise SystemExit(f"ERROR: se necesita Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior. Instálalo con: {hint}")


def run(cmd: list[str], cwd: Path = BASE_DIR) -> None:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def ensure_venv(directory: Path) -> Path:
    pyexe = venv_python(directory)
    if not pyexe.exists():
        print("[1/4] Creando entorno virtual de Python...")
        try:
            run(find_python() + ["-m", "venv", str(directory)])
        except subprocess.CalledProcessError as exc:
            hint = "" if IS_WINDOWS else "\n      En Debian/Ubuntu puede faltar: sudo apt install python3.12-venv"
            raise SystemExit(f"ERROR: no se pudo crear el entorno virtual ({exc}).{hint}") from exc
    return pyexe


def ensure_dependencies(pyexe: Path, directory: Path) -> None:
    sentinel = directory / ".deps_ok"
    if sentinel.exists():
        return
    print("[2/4] Instalando dependencias (la primera vez puede descargar ~1 GB)...")
    try:
        run([pyexe, "-m", "pip", "install", "--upgrade", "pip"])
        run([pyexe, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ERROR: falló la instalación de dependencias ({exc}).") from exc
    sentinel.write_text("ok\n", encoding="utf-8")


def ensure_frontend() -> None:
    if DIST_INDEX.exists():
        return
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("ERROR: npm no encontrado. Instala Node.js LTS (winget install OpenJS.NodeJS.LTS / sudo apt install nodejs npm).")
    print("[3/4] Compilando la interfaz web...")
    try:
        run([npm, "install", "--include=dev"], cwd=WEB_DIR)
        run([npm, "run", "build"], cwd=WEB_DIR)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ERROR: falló la compilación del frontend ({exc}).") from exc


def server_config() -> tuple[str, int]:
    host, port = "127.0.0.1", 8000
    if CONFIG_PATH.exists():
        try:
            server = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")).get("server", {})
            host = server.get("host") or host
            port = int(server.get("port") or port)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return host, port


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicia el transcriptor de reuniones.")
    parser.add_argument("--host", help="dirección de escucha (por defecto, la de data/config.json)")
    parser.add_argument("--port", type=int, help="puerto (por defecto, el de data/config.json)")
    parser.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    args = parser.parse_args()

    directory = venv_dir()
    pyexe = ensure_venv(directory)
    ensure_dependencies(pyexe, directory)
    ensure_frontend()

    host, port = server_config()
    host = args.host or host
    port = args.port or port
    url = f"http://localhost:{port}" if host in ("0.0.0.0", "::") else f"http://{host}:{port}"

    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    print(f"[4/4] Servidor en {url}  (Ctrl+C para detener)")
    try:
        run([pyexe, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)])
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: el servidor terminó con código {exc.returncode}.")
        return exc.returncode
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        sys.exit(0)
