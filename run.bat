@echo off
setlocal
cd /d "%~dp0"

set VENV=%LOCALAPPDATA%\transcriptor\venv312
set PYEXE=%VENV%\Scripts\python.exe

rem ---------- 1. Python 3.12 ----------
if not exist "%PYEXE%" (
    echo [1/4] Creando entorno virtual de Python 3.12...
    py -3.12 -m venv "%VENV%" || (
        echo ERROR: Python 3.12 no encontrado. Instalalo con:
        echo    winget install Python.Python.3.12
        pause
        exit /b 1
    )
)

rem ---------- 2. Dependencias ----------
if not exist "%VENV%\.deps_ok" (
    echo [2/4] Instalando dependencias ^(puede tardar la primera vez, descarga ~1 GB^)...
    "%PYEXE%" -m pip install --upgrade pip
    "%PYEXE%" -m pip install -r requirements.txt || (pause & exit /b 1)
    echo ok> "%VENV%\.deps_ok"
)

rem ---------- 3. Frontend ----------
if not exist "web\dist\index.html" (
    echo [3/4] Compilando la interfaz web...
    cd web
    call npm install --include=dev || (cd .. & pause & exit /b 1)
    call npm run build || (cd .. & pause & exit /b 1)
    cd ..
)

rem ---------- 4. Servidor ----------
echo [4/4] Iniciando servidor en http://localhost:8000 ...
start "" http://localhost:8000
"%PYEXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
