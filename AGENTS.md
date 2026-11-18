# AGENTS.md — Reglas para agentes en este repositorio

App web **local** (FastAPI + React) para transcribir reuniones. Se ejecuta en `127.0.0.1`. No es un servicio alojado: no agregues autenticación, multiusuario, base de datos ni Docker.

El plan maestro es `PLAN_PRODUCCION.md`. Cada tarea que recibas corresponde a un paso del plan.

## Cómo trabajar

0. Lee `docs/PROGRESS.md` si existe. Aplica las secciones **Subagentes** y **Plan de ahorro de tokens** de este archivo en toda tarea.
1. Lee la tarea completa y los archivos que menciona **antes** de editar.
2. Localiza el código **por nombre de función o clase**, no por número de línea. Las referencias `archivo:línea` del plan pueden estar desactualizadas.
3. Haz solo lo que pide la tarea. No refactorices ni "mejores" cosas fuera de alcance. Si ves un problema fuera de alcance, anótalo en el reporte final.
4. **NO ejecutes `pytest` ni ninguna suite de tests.** Los tests los corre el usuario y te pasa solo los fallos (ver sección *Pruebas*). Tú sí **escribes** los tests que la tarea pida. Como verificación barata permitida: `python -m py_compile <archivos tocados>` y, si hay `ruff` configurado, `ruff check <archivos tocados>`.
5. Un commit por tarea, con el mensaje `[<ID de tarea>] <resumen corto>`. No hagas push ni cambies de rama salvo que se pida.
6. Termina con un reporte corto: qué cambiaste, qué archivos, **los comandos exactos de test que debe correr el usuario** (primero el archivo específico, luego la suite), y dudas o riesgos pendientes.

## Cuándo parar y preguntar (no improvises)

- Un criterio de aceptación no se puede cumplir.
- Un comando, flag o API externa no existe o se comporta distinto a lo descrito en la tarea.
- Para cumplir la tarea tendrías que romper el contrato de `transcript.json` o cambiar archivos de otra tarea.
- Hay que instalar algo pesado o descargar un modelo.

En esos casos describe el problema y las opciones, y espera respuesta.

## Reglas inviolables

- **Contrato de `transcript.json`:** solo se pueden **añadir** claves. Nunca renombrar ni eliminar las existentes (incluidas `whisper_model` y `diarized`). Clips, revisión, acta, informe y frontend dependen de él.
- **Arranque vacío:** ningún modelo ni dependencia pesada (whisperx, torch, NeMo, GGUF) se descarga ni se importa al arrancar la app. Los imports pesados van **dentro** de funciones (`load()`), nunca a nivel de módulo.
- **Sin descargas implícitas:** un modelo se descarga solo por acción explícita del usuario (botón Instalar o `run.py --install`).
- **Motor por defecto:** hasta que el usuario lo cambie manualmente, el motor por defecto sigue siendo WhisperX + pyannote. Los motores nuevos son opcionales.
- **Comandos externos:** `subprocess` siempre con lista de argumentos y allow-list. Prohibido `shell=True`. Prohibido ejecutar comandos que no estén declarados en el catálogo.
- **Plantillas de prompts:** sustitución `{{VAR}}` con `.replace()`. Nunca `str.format` ni f-strings sobre el texto del prompt (contiene llaves JSON).
- **Secretos:** `api_key` y `hf_token` nunca se devuelven en claro en la API, nunca aparecen en logs ni en mensajes de error. Se enmascaran como `********`; si el PUT trae el centinela, se conserva el valor guardado.
- **Progreso y cancelación:** el progreso se reporta en la escala 0-100 con las etapas actuales (5-60 ASR, 62-94 diarización, 95 asignación, 98 guardado). Toda operación larga llama a `check_cancel()`.
- **Frontend:** reutiliza `Field`, `inputCls` y `btnPrimary` de `web/src/components.jsx`. No agregues librerías de UI ni estilos nuevos.
- **Dependencias:** no agregues dependencias al núcleo sin permiso. Las de motores van como extras en `pyproject.toml`.
- **Licencias:** NO usar pesos con licencia no comercial (CC BY-NC): Sortformer v2, DiariZen. Para diarización con Nemotron usar solo `nvidia/Nemotron-3-Diarization` (OpenMDW-1.1), nunca la variante `-preview` (licencia de evaluación).

## Subagentes para tareas repetitivas (OBLIGATORIO considerarlo)

Antes de empezar una tarea, pregúntate: **¿hay una parte mecánica, repetida y verificable?** Si la respuesta es sí, delégala a un subagente en lugar de hacerla tú en el contexto principal. El agente principal piensa, decide y verifica; el subagente ejecuta trabajo acotado.

### El subagente: `mecanico`

El subagente se llama **`mecanico`** y usa el modelo `qwen/qwen3.7-flash`. Su definición está en `mecanico.md` (se instala en el directorio de agentes de tu herramienta). Invócalo para toda tarea que cumpla los criterios de abajo.

**Restricciones de privacidad (innegociables):** el endpoint gratuito registra los prompts y salidas y los usa para mejorar los modelos del proveedor. Por eso:
- **Nunca** incluyas en un encargo ni dejes accesible al subagente: `data/`, `.env*`, `config.json` reales, claves (`api_key`, `hf_token`), audios, ni ningún `transcript.json`, acta o informe real. Todo eso contiene datos personales o secretos.
- El subagente solo recibe **código del repositorio** y fixtures sintéticos.
- Si una tarea necesita ver datos reales, la hace el agente principal, no `mecanico`.

**Límites del modelo:** es un modelo de capacidad media para trabajo mecánico; no confíes en él para diseño, seguridad ni lógica sutil. No fuerza salida JSON (los encargos piden reporte en texto). El endpoint gratuito tiene límite de peticiones: si responde con error de límite, espera o haz la tarea tú; no insistas en bucle.

### Delega (buenos candidatos)

- Aplicar **el mismo cambio** en varios sitios (por ejemplo, sustituir cada `.format(...)` por `prompts.render(...)` en varios archivos).
- Mover texto o código **literalmente** de un archivo a otro (por ejemplo, los 10 prompts a `DEFAULT_PROMPTS`).
- Escribir tests **parametrizados o repetitivos** con un patrón ya definido (un test por excepción, por motor, por perfil de hardware).
- Inventarios de solo lectura: buscar con `grep` todos los usos de algo y devolver una lista corta.
- Correr `npm run build` y devolver solo los errores (máx. 15 líneas). **Los tests nunca se delegan: no los ejecuta ningún agente.**
- Boilerplate de UI que sigue un componente existente.
- Redactar documentación a partir de datos ya verificados.

### NO delegues

- Decisiones de diseño, formato de datos o interfaces entre módulos.
- Cualquier cosa que toque el **contrato de `transcript.json`**, migraciones de configuración, seguridad, allow-lists de instalación o secretos.
- Verificar si un CLI o API externa existe (los pasos "verificación previa").
- Tareas de una sola edición pequeña: el costo de explicarlas supera el de hacerlas.
- Integración final y resolución de conflictos entre piezas.

### Cómo delegar (formato del encargo)

Cada encargo es **autocontenido** (el subagente no ve tu conversación) y usa esta plantilla:

```
OBJETIVO: <una frase>
ARCHIVOS PERMITIDOS: <lista exacta; no tocar ningún otro>
CAMBIO EXACTO: <qué hacer, con un ejemplo antes/después si es repetitivo>
NO HACER: <límites: sin refactors, sin commits, sin instalar nada>
REVISIÓN: <qué debe cumplir el resultado, comprobable leyendo el código; NO ejecutar tests>
DEVOLVER: máximo 10 líneas: archivos modificados, resultado del comando, dudas.
No pegues contenido de archivos ni diffs completos en la respuesta.
```

### Reglas para el agente principal con subagentes

1. **Un subagente = un trabajo acotado**, con un conjunto de archivos que no se solape con el de otro subagente en paralelo.
2. El subagente **no hace commit** ni toca `config.py`, `schemas.py` ni `settings.py` salvo que el encargo lo diga expresamente.
3. **Nunca confíes ciegamente en el reporte:** revisa el diff (`git diff --stat` y una lectura rápida de lo sensible). No ejecutes tests: añade a tu reporte final los comandos que el usuario debe correr.
4. Si el subagente devuelve algo fuera de lo pedido, **no lo parchees a ciegas**: corrige el encargo y relánzalo, o hazlo tú.
5. Si dos subagentes necesitan el mismo archivo, hazlos en **secuencia**, no en paralelo.
6. Las reglas inviolables de arriba aplican igual a los subagentes; inclúyelas en el encargo si son relevantes.

## Plan de ahorro de tokens

**Leer menos**
- No leas archivos enteros si solo necesitas una función: usa `grep -n` para localizarla y lee solo ese rango.
- No vuelvas a leer lo que ya leíste en esta sesión; si tuvo cambios, relee solo el fragmento afectado.
- No explores carpetas que la tarea no menciona. La tarea indica qué archivos leer.
- Al empezar una tarea, lee `docs/PROGRESS.md` (ver abajo) antes de explorar el repo.

**Escribir menos**
- Edita con reemplazos acotados (`str_replace`); no reescribas archivos completos para cambiar unas líneas.
- No repitas el plan, las reglas ni el contenido de archivos en tus mensajes.
- El reporte final tiene **máximo 15 líneas**; el de un subagente, **máximo 10**.
- Sin explicaciones largas ni resúmenes de lo obvio. Si hay una duda, formúlala en una o dos frases.

**Comandos con salida corta**
- **No corras tests.** Ahorra los tokens de leer salidas de pytest: el usuario los ejecuta y te pega solo el fallo relevante.
- Recorta salidas largas: `| tail -n 30` o `| head -n 40`. Nunca vuelques logs completos ni `pip list`.
- `git diff --stat` antes que `git diff` completo.
- Agrupa varias llamadas independientes en un solo paso cuando se pueda.

**Sesiones y contexto**
- **Una tarea por sesión.** Al terminar, deja el estado anotado y cierra; la siguiente tarea empieza limpia.
- Mantén `docs/PROGRESS.md` (máximo ~20 líneas): tarea terminada, decisiones tomadas, archivos nuevos clave, pendientes. Es el traspaso entre sesiones y evita que la siguiente reexplore el repo. Actualízalo al final de cada tarea.
- No guardes en contexto salidas largas: si necesitas un dato de un log, extrae solo esa línea.

**No gastar en bucles**
- Si un mismo error persiste tras **2 intentos** de corrección, **detente** y reporta: qué intentaste, qué falló y qué opciones ves. No sigas probando a ciegas.
- Si la tarea resulta mucho mayor de lo previsto, para y propón dividirla en lugar de ampliarla.

**Dónde sí gastar**
- Leer con cuidado el código que vas a cambiar, escribir bien el test de contrato y revisar los diffs de seguridad o configuración. Ahorrar ahí sale caro.

## Pruebas

**El usuario ejecuta los tests; el agente no.**

- Escribe los tests que la tarea pide (con adaptadores falsos y audio sintético) y déjalos listos para correr. No los ejecutes, ni siquiera "para comprobar".
- En el reporte final indica los comandos exactos, del más específico al más general. Ejemplo:
  `pytest tests/test_prompts.py -q` y después `pytest -q -x --tb=short`.
- Cuando el usuario te pase un fallo, recibirás solo esto: el nombre del test, el mensaje de error y las pocas líneas relevantes del traceback. **Trabaja solo con eso**:
  1. Localiza el código implicado con `grep -n` y lee solo ese fragmento.
  2. Corrige la causa (no el test, salvo que el test esté mal; si crees eso, dilo y explica por qué).
  3. Indica de nuevo el comando exacto para repetir **solo ese test** (`pytest tests/x.py::nombre -q`).
- Si el usuario reporta el mismo fallo tras 2 correcciones, detente y expón qué intentaste y qué opciones ves.
- Si necesitas más información del fallo, pídela con precisión (por ejemplo "pega solo las líneas 20-35 del traceback"); no pidas la salida completa.
- Nunca des una tarea por "pasando" sin que el usuario lo confirme; en el reporte di "tests escritos, pendientes de ejecutar por el usuario".
- Los tests no usan modelos reales ni red. Usan adaptadores falsos y audio sintético (silencio o tono).
- Si un test necesita modelos reales, márcalo con `@pytest.mark.integration` (se ejecuta solo a mano).
- Todo comportamiento nuevo lleva su test.

## Estilo

- Python: tipado en funciones públicas, `ruff` limpio si está configurado. Español en mensajes al usuario; nombres de código en inglés como el resto del repo.
- Errores al usuario: claros y accionables (qué falló y qué hacer).
- No dejes `print` de depuración ni código comentado.