# Progreso

- P1-1–P1-5: config v2, prompts/clientes LLM, jobs review/meeting/report, extracción JSON y contratos preservados; tests escritos, pendientes de ejecución.
- P1-6–P1-7: ajustes de modelos/prompts, secretos con centinela y prueba Ollama; revisión pendiente de prueba manual y persistencia tras reinicio.
- Pendiente previo: `npm run build` requiere instalar dependencias web; no se instalaron.
- P2-0: pyproject y contrato de transcript con fixtures sintéticos; tests pendientes del usuario.
- P2-1: puertos audio y chunking; tests sintéticos pendientes.
- P2-2: interfaces y adaptadores WhisperX/pyannote/none; imports pesados dentro de `load()`; tests falsos pendientes.
- P2-3: orquestador `app/services/transcription.py`; progreso/cancelación preservados y contrato `transcript.json` ampliado solo con claves nuevas.
- P2-4: config/schema v3 con engine/options, migración v1/v2 y mirrors legacy para la UI actual; `hf_token` se conserva y enmascara en `options.pyannote`.
- Registro perezoso de adaptadores; el router llama al orquestador y `diar.engine=none` omite diarización.
- Tests de migración, defaults, secretos, validación de options y transcript sin hablantes escritos; pendientes de ejecución por el usuario.
- P2-5: adaptador opcional Parakeet GGUF, ruta local, salida JSON y chunking; tests sintéticos/de integración escritos. Runtime y modelo se verificaron localmente; prueba manual documentada en `tests/test_parakeet_gguf.py`.
- P2-6: adaptador Nemotron GGUF usa solo `nvidia/Nemotron-3-Diarization` (OpenMDW-1.1); tests simulados escritos, modelo no descargado.
- Decisión P2-7: NeMo-Speech.cpp y modelos GGUF se instalan manualmente; no ejecutar scripts remotos ni instalar binarios desde API/CLI.
- P2-7: catálogo, recomendaciones, detección sin torch, extras Python opcionales, consentimiento HF para ambos modelos pyannote y CLI `--install`; tests en `tests/test_catalog.py`, pendientes del usuario.
- WhisperX 3.3.1 requiere `pyannote.audio==3.3.2`; `speaker-diarization-3.1` y `segmentation-3.0` declaran MIT. Sin cambios al motor default.
- P2-7: `python3 -m pytest tests/test_catalog.py -q` confirmado por el usuario: 6 passed; 3 avisos deprecados de Starlette/httpx y FastAPI `on_event`.
- `py_compile` y `git diff --check` pasaron; suite completa pendiente de ejecución por el usuario.
- Pytest está instalado solo en `.venv` y no se ejecutó por regla del repo.
