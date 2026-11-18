# Progreso

- Tarea completada: P1-1, esquema de configuración v2 y migración desde v1.
- Decisiones: `llm.tasks` conserva los max_tokens por job actuales y usa timeout 180; `prompts` contiene las cinco plantillas de usuario y cinco claves system con `{system, user}` vacíos.
- GET/PUT enmascara `api_key` y `hf_token`; el centinela en PUT conserva el secreto almacenado.
- Archivos clave P1-1: `app/config.py`, `app/schemas.py`, `app/routers/settings.py`, `tests/test_config_settings.py`.
- Tarea completada: P1-2, registro seguro de prompts con defaults literales, variables requeridas, render por reemplazo y validación de longitud.
- Archivos clave: `app/services/llm/prompts.py`, `tests/test_prompts.py`; los jobs siguen sin integrar el registro (P1-4).
- Verificación sintáctica: `python3 -m py_compile app/services/llm/prompts.py tests/test_prompts.py`; tests escritos, pendientes de ejecutar por el usuario.
- Tarea completada: P1-3, cliente LLM con overrides por tarea, descubrimiento de modelos Ollama/OpenAI-compatible y endpoints LLM/prompts.
- Archivos clave: `app/services/llm/client.py`, nuevo `app/routers/llm.py`, registro en `app/main.py`, `tests/test_llm.py`.
- `PROVIDERS.get` evita KeyError por provider desconocido; `list_models` registra errores sin propagar excepción y devuelve `[]`.
- Tests escritos para overrides, parseo `/api/tags`, provider desconocido, reset de prompt y Ollama no disponible; pendientes de ejecutar por el usuario.
- Tarea completada: P1-4, jobs review/meeting/report integrados con prompts configurables y overrides por fase; límites del informe editables.
- Tests de contrato de prompts y configuración escritos; pendientes de ejecución por el usuario.
- Tarea completada: P1-5, extractor JSON común tolera fences, texto envolvente y comas finales; un reintento estricto en fallo de parseo.
- Decisión P1-5: report ahora pide JSON con `notes`/`markdown`, extraídos para conservar exactamente `report_work.json` y `informe.md.json`; review/meeting conservan sus claves de salida.
- Errores terminales identifican etapa y modelo, sugieren modelo mayor/revisar prompt y escalan al gestor para finalizar el job como error.
- Archivos clave P1-5: `app/services/llm/json_utils.py`, jobs LLM, `app/services/llm/prompts.py`, `tests/test_llm_json_utils.py`, `tests/test_llm_job_prompts.py`.
- Verificación sintáctica con `python3 -m py_compile`; tests escritos, pendientes de ejecutar por el usuario.
