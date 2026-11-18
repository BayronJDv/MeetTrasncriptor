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
- Verificación estática: `python3 -m py_compile` y `git diff --check`; pytest no ejecutado.
