# Plan de migración a producción

## Principios

1. Arranque **vacío**: se instala solo el núcleo (FastAPI/React); ningún modelo ni dependencia pesada (whisperx, torch, NeMo, binarios de modelo) se descarga sin acción explícita del usuario.
2. **Catálogo + recomendador**: la app detecta el hardware y sugiere motores; al elegirlos muestra requisitos (token de Hugging Face, aceptación de términos de pyannote, RAM/VRAM, licencia) antes de instalar.
3. **Contrato estable**: `transcript.json` conserva su forma actual (`app/services/whisperx_service.py:199-212`); clips, revisión, acta, informe y frontend no se rompen.
4. **Fases independientes**: cada fase termina con la app funcionando y los tests pasando.
5. App web local (127.0.0.1). El motor por defecto sigue siendo WhisperX + pyannote hasta que el usuario valide manualmente los motores nuevos.
## Por qué estos modelos (investigación 2026)

| Necesidad | Recomendación | Por qué | Licencia / requisito |
|---|---|---|---|
| ASR español, hardware modesto | **Parakeet TDT 0.6B v3**, GGUF Q8 vía `NeMo-Speech.cpp` | 25 idiomas incluido español, WER ~3,4-3,7 % en FLEURS/es, timestamps de palabra nativos, >1× tiempo real en CPU, ~0,7 GB | CC-BY-4.0 (atribución), sin token HF |
| ASR multilenguaje / 99 idiomas | **WhisperX large-v3-turbo** (o faster-whisper) | La opción segura si entran otros idiomas; hoy se usa `small` int8 | MIT/Apache; la diarización asociada necesita token HF |
| ASR alternativa permisiva | **Qwen3-ASR 0.6B/1.7B** | Apache-2.0, 52 idiomas, español ~3,3-3,8 % | ~0,8-2 GB, más pesada que Parakeet |
| Descartadas | SenseVoice (no cubre español, licencia no OSI), DiariZen/Sortformer v2 (pesos CC BY-NC) | — | — |
| Diarización | **Nemotron-3-Diarization** (100 M, hasta 8 hablantes) | Voice Arena: DER 14,7 % vs 30,6 % de pyannote community-1; corre con Transformers, NeMo o GGUF | OpenMDW-1.1, uso comercial OK; verificar acceso a los pesos |
| Diarización actual | pyannote community-1.  | Sin límite de hablantes, pero token HF y términos gateados; lenta en CPU.  | CC-BY-4.0 |

`NeMo-Speech.cpp` tiene instaladores en Linux/macOS/Windows y soporta Parakeet v3 y Nemotron-3. también incluye Sortformer v2 que son prohibidos, nunca se deben cargar. Es un proyecto joven: se deja como adaptador opcional, nunca como único camino.

---

## Fase 1 — LLM local (Ollama) + prompts editables

### Paso 1.1 — Esquema de configuración v2 con migración

- `app/config.py:18-51`: añadir `schema_version: 2`; `llm.tasks` con 5 entradas (`review`, `meeting_1`, `meeting_2`, `report_1`, `report_2`), cada una con `model: null` (hereda el global), `max_tokens` y `timeout`; `prompts` con 10 entradas `{system, user}`; mantener las claves antiguas.
- `app/config.py:61-103`: función `_migrate_v1(cfg)` invocada desde `load_config()` tras el deep-merge: convierte configuraciones sin `schema_version`, preserva `api_key` y rellena los defaults nuevos. El backup por JSON corrupto (`config.py:74-89`) queda intacto.
- `app/schemas.py:28-48`: nuevos submodeles opcionales (`LlmTaskSettings`, `PromptSettings`) y corregir el desfase de `model` (`schemas.py:31` dice `llama-3.3-70b-versatile`, `config.py:37` dice `openai/gpt-oss-120b`). Los `model_dump(exclude_none=False)` actuales no deben borrar valores no enviados.
- `app/routers/settings.py:68-76`: añadir las secciones nuevas a la lista editable. En `GET /api/settings` devolver `api_key` y `hf_token` enmascarado (`********`) y en PUT conservar el valor anterior si llega el centinela.

### Paso 1.2 — Registro de prompts seguros

- Crear `app/services/llm/prompts.py`: mover literalmente los 10 textos desde `review.py:18-39`, `meeting.py:15-39`, `report.py:17-37` y los sistemas en línea `meeting.py:84,111` y `report.py:99,137` a `DEFAULT_PROMPTS`.
- Definir `REQUIRED_VARS` por prompt: `review_user → {segments, max_suggestions}`; `meeting_1 → {win_lo, win_hi, segments}`; `meeting_2 → {parts}`; `report_1 → {win_lo, win_hi, segments}`; `report_2 → {template_block, meeting_block, notes, instructions_block}`; sistemas → `{}`.
- `render(name, **vars)` con sustitución `{{VAR}}` mediante `.replace()` (nunca `str.format`: los ejemplos JSON tienen llaves sueltas y revientan al editarlos). `validate(name, system, user)` comprueba variables y longitudes.
- `get_prompt(name)` lee `config["prompts"][name]` con fallback a `DEFAULT_PROMPTS`.

### Paso 1.3 — Cliente LLM y descubrimiento Ollama

- `app/services/llm/client.py:17-49`: verificar el catálogo `ollama` (`http://localhost:11434/v1`, sin key); usar `PROVIDERS.get(...)` en vez de indexación directa para evitar `KeyError` con configuración editada a mano.
- `client.py:56-117`: usar de verdad el gancho `LlmClient(overrides)` existente: resolver `model`, `max_tokens` y `timeout` por tarea con fallback al global. El timeout deja de ser el `180` fijo.
- Nuevo `list_models(provider, base_url, api_key)`: para Ollama, `GET {host}/api/tags` (devuelve `models[].name`); para OpenAI-compatible, `GET /models`. Devolver `[]` con error claro si el servicio no responde.
- `app/routers/llm.py`: `GET /api/llm/models?provider=ollama`, `POST /api/llm/test`, `GET /api/prompts`, `PUT /api/prompts`, `POST /api/prompts/{name}/reset`. Registrar en `app/main.py:14,28-37`.

### Paso 1.4 — Conectar los jobs

- `review.py:165`, `meeting.py:62`, `report.py:73`: pasar `overrides` con la tarea correspondiente.
- Sustituir los `.format(...)` de `review.py:179`, `meeting.py:76,112` y `report.py:91,138` por `prompts.render(...)`.
- Exponer `max_suggestions` (`review.py:181`) y los límites de caracteres (`report.py:120,127,130,141`) como claves de configuración avanzada, conservando los valores actuales por defecto.

#### Paso 1.4b
Parseo robusto de JSON del LLM (extraer de cercas, tolerar comas finales, 1 reintento, error claro)

### Paso 1.5 — Interfaz

- `web/src/pages/Settings.jsx:148-191`: desplegable de tareas con modelo por tarea (datalist alimentado por `/api/llm/models`), botón "Probar conexión" y aviso si Ollama no está instalado, con el comando `ollama pull <modelo>`.
- Nuevo `web/src/components/settings/PromptEditor.jsx`: pestaña por etapa, dos `<textarea className={inputCls}>`, lista de variables disponibles, validación en vivo y botón "Restaurar default". Integrarlo en `Settings.jsx` antes del botón guardar (línea 193) y enviar `prompts` dentro del PUT de `/settings`.
- Seguir `Field`/`inputCls`/`btnPrimary` de `web/src/components.jsx:127-145`. Sin estilos nuevos.

### Paso 1.6 — Verificación

- `pytest`: migración v1→v2 preserva claves y `api_key`; `render` con llaves JSON literales; `validate` rechaza variable faltante; el override de tarea gana sobre el global; parser de `/api/tags`; reset restaura el texto original.
- **Aceptación**: con Ollama apagado la app arranca y los jobs dan un error claro; con Ollama encendido cada etapa usa su modelo configurado; los prompts se editan y sobreviven a un reinicio.

---

## Fase 2 — Motores ASR/diarización intercambiables e instalación guiada

revisar [Plan fase 2](./Fase2.md)
---

## Fase 3 — Endurecimiento production

1. **Dependencias y arranque**: `pyproject.toml` con core fijado y extras (`.[asr-whisperx]`, `.[diar-pyannote]`, `.[asr-parakeet]`, `.[diar-nemotron]`), lockfile, `run.py` instala solo el core y `--install <extra>` bajo demanda; reescribir `README.md:28-39`.
2. **Tests**: `pytest` con `conftest.py`, audio sintético (silencio/tono) y adapters falsos; tests de API con `TestClient`; tests de prompts y migración; marcar `pytest.mark.integration` los que necesiten modelos reales y ejecutarlos solo de forma manual.
3. **Errores y observabilidad**: excepciones neutrales (`EngineNotInstalled`, `MissingCredentials`, `ModelLoadError`, `EngineCancelled`) mapeadas en `app/jobs.py:131-138`; `logging` estructurado con nivel configurable; `GET /api/health` incluye estado de motores y Ollama; `GET /api/system` sin importar `torch` en el router.
4. **Seguridad**: clave de API enmascarada, CORS limitado a localhost (ya en `app/main.py:21-26`), allow-list de comandos de instalación, validación Pydantic al cargar configuración, permisos de archivos y sin secretos en logs.
5. **Rendimiento**: caché de modelos con ciclo de vida explícito (hoy `whisperx_service.py:15` es un dict a nivel de módulo), tamaño de chunk por perfil, reintento GPU→CPU centralizado y timeouts configurables.
6. **Documentación**: matriz de modelos con licencias y atribución CC-BY, guía de prompts y variables, guía de instalación por hardware, notas de migración de `data/config.json` y troubleshooting Ollama/HF/nemo-speech.
7. **CI**: workflow que ejecute `pytest`, `ruff`, `mypy` y `npm run build` en `web/`.

## Fuera de alcance

Multiusuario/autenticación, base de datos, captura de micrófono, streaming en vivo, fine-tuning, embeddings y dockerización.

## Riesgos y verificaciones pendientes

No se verificó el rendimiento real con audios en español ni la descarga GGUF de Nemotron sin token: los benchmarks citados son principalmente en inglés. Si la precisión en español de Nemotron defrauda, pyannote se mantiene como motor seleccionable sin tocar código.
