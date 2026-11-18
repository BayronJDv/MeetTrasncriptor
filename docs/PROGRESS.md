# Progreso

- P1-1: configuración v2 y migración; `llm.tasks`, prompts `{system,user}`, secretos enmascarados y centinela de PUT. Archivos: `app/config.py`, `app/schemas.py`, `app/routers/settings.py`, tests de configuración.
- P1-2: registro de prompts, defaults, variables requeridas, render por reemplazo y validación. Archivos: `app/services/llm/prompts.py`, `tests/test_prompts.py`.
- P1-3: cliente LLM, overrides por tarea, descubrimiento y endpoints LLM/prompts; errores de listado devuelven `[]`. Archivos: `app/services/llm/client.py`, `app/routers/llm.py`, `app/main.py`, `tests/test_llm.py`.
- P1-4: jobs review/meeting/report integrados con prompts configurables y overrides por fase; límites del informe editables.
- P1-5: extracción JSON robusta y reintento; report conserva contratos `report_work.json`/`informe.md.json`; errores terminales identifican etapa y modelo.
- Tests de P1-1–P1-5 escritos; pendientes de ejecución por el usuario. Verificación sintáctica previa con `python3 -m py_compile`.
- Tarea completada: P1-6, controles de modelos por tarea, descubrimiento y prueba de conexión LLM; el fallo de Ollama muestra `ollama pull <modelo>`.
- Editor de prompts por cinco etapas integrado en ajustes, con validación en vivo y restauración de defaults; envía `prompts` junto al PUT `/settings`.
- Secretos conservan el centinela `********` al guardar; el frontend no muestra valores API key/HF token.
- Archivos clave P1-6: `web/src/pages/Settings.jsx`, nuevo `web/src/components/settings/PromptEditor.jsx`.
- Verificación pendiente: `npm run build` no pudo arrancar porque `web/node_modules/.bin/vite` no está instalado; no se instalaron dependencias. Tests/build pendientes de ejecutar por el usuario.
- P1-7: inventario por nombres confirma casos de P1-1–P1-5 y seis criterios de test del paso 1.6; añadido caso de persistencia de prompts al recargar config en `tests/test_llm.py`.
- Revisión de P1-7 no encontró defectos funcionales verificables; pendiente prueba manual Ollama apagado/encendido, modelos por etapa, persistencia tras reinicio y migración v1 conservando `api_key`.
- P2-0: añadido `pyproject.toml` con dependencias actuales y extras vacíos; `requirements.txt` permanece sin cambios.
- Añadidos `tests/conftest.py` (audio sintético silencio/tono), `tests/fixtures/transcript_example.json` y `tests/test_transcript_contract.py`; cubre el formato escrito por `whisperx_service` y cualquier `data/projects/*/transcript.json`.
- Configurado marcador `integration`; contrato revisa transcripciones presentes sin parametrización vacía ni skips; pendiente de ejecución por el usuario. Sintaxis comprobada con `python3 -m py_compile tests/conftest.py tests/test_transcript_contract.py`.
- P2-1: tipos neutrales de audio, decodificación FFmpeg a PCM float32 mono y chunking separados de WhisperX; servicio conserva el flujo actual.
- Añadidos tests sintéticos para `snap_boundary` y `compute_chunks` en `tests/test_audio_chunking.py`; pendientes de ejecución por el usuario.
