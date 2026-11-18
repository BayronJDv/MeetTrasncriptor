# Progreso

- Tarea completada: P1-1, esquema de configuración v2 y migración desde v1.
- Decisiones: `llm.tasks` conserva los max_tokens por job actuales y usa timeout 180; `prompts` contiene las cinco plantillas de usuario y cinco claves system con `{system, user}` vacíos.
- GET/PUT enmascara `api_key` y `hf_token`; el centinela en PUT conserva el secreto almacenado.
- Archivos clave: `app/config.py`, `app/schemas.py`, `app/routers/settings.py`, `tests/test_config_settings.py`.
- Verificación sintáctica con `python3 -m py_compile`; tests escritos, pendientes de ejecutar por el usuario.
- Tarea completada: P1-2, registro seguro de prompts con defaults literales, variables requeridas, render por reemplazo y validación de longitud.
- Archivos clave: `app/services/llm/prompts.py`, `tests/test_prompts.py`; los jobs siguen sin integrar el registro (P1-4).
- Verificación sintáctica: `python3 -m py_compile app/services/llm/prompts.py tests/test_prompts.py`; tests escritos, pendientes de ejecutar por el usuario.
- Tarea completada: P1-3, cliente LLM con overrides por tarea, descubrimiento de modelos Ollama/OpenAI-compatible y endpoints LLM/prompts.
- Archivos clave: `app/services/llm/client.py`, nuevo `app/routers/llm.py`, registro en `app/main.py`, `tests/test_llm.py`.
- `PROVIDERS.get` evita KeyError por provider desconocido; `list_models` registra errores sin propagar excepción y devuelve `[]`.
- Tests escritos para overrides, parseo `/api/tags`, provider desconocido, reset de prompt y Ollama no disponible; pendientes de ejecutar por el usuario.
- Pendiente: P1-4 conexión de jobs y uso de prompts registrados.
