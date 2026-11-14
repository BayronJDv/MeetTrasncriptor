# Transcriptor de reuniones (local)

Programa de escritorio (web local) para **transcribir audios largos (~3 h)** con identificación de
hablantes, corregirlos con ayuda de IA y **generar informes** a partir de una plantilla.

Todo el procesamiento de audio es **100% local** (WhisperX + pyannote); la IA solo se usa para
revisión de texto y redacción del informe (Groq u otro proveedor configurable).

## Flujo de trabajo

1. **Transcripción** — Subes el audio; verás el progreso en vivo por etapas
   (transcribiendo por tramos → alineando → diarizando → asignando voces).
2. **Hablantes** — El programa sugiere clips de audio de cada voz detectada (`SPEAKER_00…`).
   Escuchas los clips, escribes el nombre real de cada hablante y se propaga a toda la
   transcripción. También puedes corregir el hablante de un segmento concreto.
3. **Revisión IA** — Un LLM (Groq por defecto) recorre toda la transcripción buscando
   incoherencias típicas de ASR (p. ej. *"conduci mi barro"*). Aparece una lista de sugerencias:
   haces clic, escuchas ese fragmento exacto y aceptas / editas / rechazas.
4. **Estructura de la reunión** (opcional) — La IA identifica temas, decisiones, **votaciones**,
   compromisos y conclusiones; el esquema es editable.
5. **Informe** — Subes una plantilla (`.md`, `.txt` o `.docx`) o escribes indicaciones libres.
   La IA redacta el informe y lo descargas en **.docx** o **.md**.

## Instalación

Requisitos (una sola vez):

- **Python 3.12** → `winget install Python.Python.3.12`
- **Node.js** (para compilar la interfaz una vez) → `winget install OpenJS.NodeJS.LTS`
- **Visual C++ Redistributable** (requisito de PyTorch en Windows) →
  `winget install Microsoft.VCRedist.2015+.x64`

Después, simplemente ejecuta **`run.bat`**: crea el entorno virtual, instala dependencias,
compila la interfaz y abre `http://localhost:8000`.

> El entorno virtual de Python se crea en `%LOCALAPPDATA%\transcriptor\venv312` (fuera de
> OneDrive) para no sincronizar gigas de librerías. Los audios y resultados sí quedan en
> `data/` dentro del proyecto: si no quieres que OneDrive los suba, marca esa carpeta como
> excluida en Ajustes de OneDrive.

### Token de HuggingFace (necesario para la diarización)

1. Crea una cuenta gratis en [huggingface.co](https://huggingface.co) y genera un token de
   acceso en *Settings → Access Tokens*.
2. Acepta los términos de uso del modelo
   [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1).
3. Pega el token en **Ajustes → Diarización** (se descarga el modelo la primera vez).

### IA (Groq u otro)

- **Groq** (recomendado): crea una API key gratis en [console.groq.com](https://console.groq.com)
  y pégala en **Ajustes → IA**.
- También soportados: **Google Gemini**, **OpenRouter** (modelos :free), **Ollama** (local) y
  cualquier endpoint compatible con OpenAI.

## Rendimiento en este equipo (MX150 2 GB · 16 GB RAM)

| Etapa | Configuración | Audio de 3 h aprox. |
|---|---|---|
| ASR (Whisper `small`, CPU int8) | por defecto | 45–90 min |
| Diarización (pyannote) | GPU MX150 si hay torch-CUDA; si no, CPU | 20–40 min (GPU) / 2–4 h (CPU) |
| Revisión IA (Groq) | concurrencia 2 | 5–15 min |

Consejos:
- `small` + `int8` + CPU es el punto dulce de este equipo; `medium` mejora calidad pero triplica
  el tiempo.
- Para acelerar la diarización con la GPU: `pip install torch --index-url https://download.pytorch.org/whl/cu121`
  en el venv y elige **GPU (CUDA)** en Ajustes (la app reintenta en CPU si la GPU se queda sin memoria).

## Estructura del proyecto

```
run.bat                  # arranca todo
requirements.txt         # dependencias Python
app/                     # backend FastAPI (API + jobs + servicios)
web/                     # frontend React (compilado a web/dist)
data/                    # config.json + data/projects/<id>/ (audio, transcript.json, clips/, informe.md)
templates/               # tus plantillas de informe
```

## Desarrollo

```bat
:: backend con recarga
%LOCALAPPDATA%\transcriptor\venv312\Scripts\python -m uvicorn app.main:app --reload

:: frontend con recarga (proxy a :8000)
cd web && npm run dev
```
