# Progreso

- Tarea completada: P1-1, esquema de configuración v2 y migración desde v1.
- Decisiones: `llm.tasks` conserva los max_tokens por job actuales y usa timeout 180; `prompts` contiene las cinco plantillas de usuario y cinco claves system con `{system, user}` vacíos.
- GET/PUT enmascara `api_key` y `hf_token`; el centinela en PUT conserva el secreto almacenado.
- Archivos clave: `app/config.py`, `app/schemas.py`, `app/routers/settings.py`, `tests/test_config_settings.py`.
- Verificación sintáctica con `python3 -m py_compile`; tests escritos, pendientes de ejecutar por el usuario.
- Pendiente: P1-2 llena e integra las plantillas de prompts.
