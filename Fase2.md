# Fase 2 — Motores ASR/diarización intercambiables e instalación guiada

**Alcance:** app web local (`127.0.0.1`). Sin multiusuario, autenticación, base de datos ni Docker.

**Reglas que gobiernan toda la fase** (detalle en `AGENTS.md`):

- `transcript.json` solo recibe claves **nuevas**; nunca se renombra ni elimina nada existente.
- El motor por defecto sigue siendo **WhisperX + pyannote** hasta que el usuario decida cambiarlo tras validarlo a mano (paso 2.9).
- Arranque vacío: ningún modelo ni dependencia pesada se descarga ni se importa al arrancar.
- Las referencias `archivo:línea` son aproximadas; localiza el código por nombre de función.

## Estructura y orden

| Subfase | Pasos | Tareas | Resultado |
|---|---|---|---|
| Base | 2.0 | P2-0 | pytest y test de contrato listos |
| **2a** Refactor | 2.1 – 2.4 | P2-1 … P2-4 | Misma app, misma calidad, ahora con puertos y adaptadores. **Sin motores nuevos.** |
| **2b** Motores nuevos | 2.5 – 2.6 | P2-5, P2-6 | Parakeet y Nemotron disponibles (opcionales) |
| **2c** Producto | 2.7 – 2.9 | P2-7 … P2-9 | Catálogo, instalación guiada, UI y aceptación |

Cada paso termina con la app funcionando y los tests en verde. **El agente escribe los tests pero no los ejecuta: los corre el usuario** y le reporta solo los fallos. Los pasos son **secuenciales** (todos tocan `config.py`, `schemas.py` o el orquestador), salvo 2.5 y 2.6, que pueden hacerse en paralelo.

---

## Paso 2.0 — Base de pruebas y contrato (P2-0)

- Crear `pyproject.toml` con el núcleo (las dependencias actuales de `requirements.txt`) y extras **vacíos**: `asr-whisperx`, `diar-pyannote`, `asr-parakeet`, `diar-nemotron`. `requirements.txt` sigue funcionando.
- Configurar `pytest`: `conftest.py`, generador de audio sintético (silencio/tono) y marcador `integration` para pruebas con modelos reales (solo manuales).
- **Test de contrato de `transcript.json`:** lista de claves y tipos tal como los escribe hoy el código (`segments`, palabras, `speaker`, tiempos, `whisper_model`, `diarized`, etc., verificadas en el código real) y un test que valida cualquier `transcript.json` contra ella, con un fixture de ejemplo.
- **Criterio:** el test de contrato queda escrito y, al ejecutarlo el usuario, pasa. Este test protege todo lo que sigue.

---

# Subfase 2a — Refactor a puertos (sin motores nuevos)

## Paso 2.1 — Puertos y tipos neutrales (P2-1)

- Crear `app/services/audio/ports.py` con dataclasses y alias: `AudioBuffer(samples, sample_rate, duration)`, `Word`, `Segment`, `Turn`, `AsrResult`, `EngineInfo`, `ProgressFn(stage, fraction, detail)` y `CancelFn()`. Solo tipos, sin lógica.
- Crear `app/services/audio/chunking.py` moviendo `snap_boundary`/`compute_chunks` y la decodificación a 16 kHz (hoy en `whisperx_service.py` y `ffmpeg_utils.py`). La carga y concatenación de audio deja de depender de `whisperx.load_audio` y usa `ffmpeg_utils`.
- `whisperx_service.py` importa desde `chunking.py`; su comportamiento no cambia.
- **Criterio:** tests verdes al ejecutarlos el usuario (incluido el contrato), tests nuevos de `compute_chunks`/`snap_boundary`, y la transcripción actual sigue funcionando.

## Paso 2.2 — Adaptadores de los motores actuales (P2-2)

- Definir una interfaz mínima de motor: `load()`, `transcribe()`/`diarize()`, `unload()`, `info() → EngineInfo`.
- `engines/asr/whisperx.py`: migrar la lógica de ASR **sin cambios de comportamiento**, incluidos los fallbacks de alineación. `import whisperx` solo dentro de `load()`.
- `engines/diar/pyannote.py`: migrar la diarización; devolver `list[Turn]` en lugar de DataFrame; conservar el fallback GPU→CPU por OOM y el callback de progreso.
- `engines/speaker_assignment.py`: portar `assign_word_speakers` a una función neutral (palabras + `list[Turn]`) con degradación segura si falla.
- `engines/diar/none.py`: no-op (lista vacía) para quien no tenga token de Hugging Face.
- **Criterio:** tests con librerías falsas (monkeypatch) del fallback GPU→CPU y de la degradación de la asignación; importar un adaptador **no** importa `whisperx` ni `torch`.

## Paso 2.3 — Orquestador fuera de los adaptadores (P2-3)

- Crear `app/services/transcription.py` con el flujo actual reescrito contra los puertos: resolver motores → cargar → transcribir por chunk → alineación opcional → diarización → asignación de hablantes → escribir `transcript.json` → `meta.json`.
- Escala de progreso y etapas **idénticas**: 5-60 ASR, 62-94 diarización, 95 asignación, 98 guardado (no se toca el SSE del frontend ni `app/jobs.py`).
- Llamar a `check_cancel()` en cada operación larga: carga de modelo, decodificación, cada chunk, alineación, diarización y guardado (hoy solo hay 3 puntos).
- En `transcript.json` **añadir** `engine` y `model`; conservar `whisper_model` y `diarized`.
- Por ahora resuelve siempre `whisperx` + `pyannote`.
- **Criterio:** con adaptadores **falsos**: el contrato se cumple, el progreso queda en 0-100 y es monótono, la cancelación funciona en cada etapa y sin diarización el resultado sigue siendo válido.

## Paso 2.4 — Configuración v3 y conexión del router (P2-4)

- `config.py`/`schemas.py`: añadir `asr.engine`, `diar.engine`, `asr.options` y `diar.options` (diccionarios libres validados por el adaptador). Defaults: `whisperx` y `pyannote`.
- Migración v2→v3: mover `asr.model/device/compute_type/batch_size/chunk_minutes` a `asr.options.whisperx`, y `hf_token/min_speakers/...` a `diar.options.pyannote`. Preservar y **enmascarar** `hf_token` (igual que `api_key`).
- Registro de motores: diccionario `id → clase de adaptador` con import perezoso.
- `app/routers/transcribe.py`: dejar de importar la implementación concreta y llamar a `transcription.run(...)`, que elige adaptadores según la config.
- **Criterio:** configs v1 y v2 migran a v3 sin perder datos; con la config por defecto el comportamiento es idéntico al anterior; `diar.engine = "none"` produce un `transcript.json` válido sin hablantes.

**Puerta de 2a:** la app funciona exactamente como antes. Si no, no se pasa a 2b.

---

# Subfase 2b — Motores nuevos (opcionales)

## Paso 2.5 — Adaptador Parakeet vía NeMo-Speech.cpp (P2-5)

**Verificación previa obligatoria** (sustituye a una Fase 0): antes de escribir código, confirmar en la documentación oficial del CLI de NeMo-Speech.cpp (o con `nemo-speech --help`): (a) el subcomando de transcripción, (b) si existe salida JSON con timestamps por palabra y con qué flag, (c) qué modelo Parakeet multilingüe (v3, español) existe en GGUF y cómo se descarga. Si algo no existe o difiere, **detenerse y reportar**; no inventar flags.

- `engines/asr/parakeet_gguf.py`: `subprocess` con lista de argumentos y comando en allow-list (sin `shell=True`); parsear palabras/timestamps a `AsrResult`; detectar el binario con `shutil.which` y, si falta, lanzar un error claro de "motor no instalado".
- Reutilizar `chunking.py` para audios largos; respetar `check_cancel()` (matar el proceso hijo al cancelar) y el progreso.
- Registrar como `parakeet_gguf`. **No** es el motor por defecto.
- Atribución: CC-BY-4.0 (se muestra en catálogo y "Acerca de").
- **Criterio:** tests con salida simulada: parseo correcto, binario ausente → error claro, cancelación mata el proceso, audio largo se divide. Test `integration` opcional con el binario real.

## Paso 2.6 — Adaptador de diarización Nemotron-3 vía NeMo-Speech.cpp (P2-6)

**Verificación previa obligatoria:** confirmar en la documentación oficial: (a) subcomando de diarización, (b) formato de salida estructurada (inicio/fin/hablante) y su flag, (c) que exista un GGUF de `nvidia/Nemotron-3-Diarization` (modelo **final**, OpenMDW-1.1; no la variante `-preview` ni Sortformer v2, de licencia restrictiva) y cómo se descarga. Si no existe, **detenerse y reportar**.

- `engines/diar/nemotron_gguf.py`: `subprocess` seguro (igual que 2.5) → `list[Turn]`. El identificador del modelo Nemotron-3 final queda fijado en código/catálogo para que sea imposible cargar Sortformer v2 por accidente.
- Límite de 8 hablantes: si el resultado supera 8 o se esperan más, advertencia visible y sugerencia de usar pyannote. Nota de calidad: Nemotron rinde mejor en reuniones de 5-8 personas; en diálogos de 2 puede rendir peor que pyannote.
- Registrar como `nemotron_gguf`. **No** es el default.
- **Criterio:** tests con salida simulada: parseo a `Turn`, binario ausente → error claro, más de 8 hablantes → advertencia, cancelación correcta.

**Puerta de 2b:** los motores nuevos funcionan con adaptadores reales **o** la tarea se detuvo con un reporte claro. En ambos casos la app sigue funcionando con WhisperX + pyannote.

---

# Subfase 2c — Catálogo, instalación e interfaz

## Paso 2.7 — Catálogo, recomendador e instalación guiada (P2-7)

- `app/services/catalog.py` + `app/routers/catalog.py`: `GET /api/catalog` con `{id, kind, label, license, requirements[], hardware_tier, installed, install_hint}`. Requisitos tipados: `hf_token`, `hf_terms(url)`, `ram_gb`, `vram_gb`, `pip_extra`, `binary`. Incluye `whisperx`, `pyannote`, `parakeet_gguf`, `nemotron_gguf` y `none`.
- Ampliar `/system` con `cpu`, `ram_gb`, `vram_gb`, `os`, capacidades detectadas y `recommendations` en 3 perfiles:
  - **CPU / ≤2 GB de RAM libre:** Parakeet GGUF + Nemotron GGUF; alternativa WhisperX `small` int8 si necesita 99 idiomas.
  - **GPU NVIDIA ≥6 GB:** WhisperX o Parakeet según lo instalado.
  - **pyannote (cualquier equipo):** requiere token HF y aceptar términos; mostrar la URL del modelo y exigir confirmación "Acepto los términos" antes de marcarlo instalado.
- `/system` y el catálogo **no importan `torch`**; detectar GPU con `nvidia-smi` (subprocess seguro).
- `POST /api/engines/{id}/install` como job (`manager.submit`), ejecutando **solo** comandos declarados en el catálogo (allow-list): `pip install` **no editable** de un extra del `pyproject`, o el instalador oficial del binario. El `id` se valida contra el catálogo. También `run.py --install <id>` por CLI.
- Rellenar los extras del `pyproject.toml` con las dependencias reales; `requirements.txt` queda reducido al núcleo.
- **Criterio:** recomendaciones por perfil (con hardware simulado); un `id` desconocido se rechaza; no se puede inyectar un comando; `/system` y el catálogo funcionan sin librerías pesadas instaladas; la app recién clonada no descarga nada.

## Paso 2.8 — Interfaz de motores (P2-8)

- Crear `web/src/components/settings/EnginePanel.jsx`: dos selectores (ASR y diarización) desde `/api/catalog`; checklist de requisitos con enlaces; estado instalado / no instalado; botón "Instalar" con progreso y errores claros; banner con la recomendación de hardware; checkbox "Acepto los términos" para pyannote; atribución CC-BY del motor elegido.
- Integrarlo en `Settings.jsx`.
- `Process.jsx`: en "Configuración activa" mostrar los nombres reales de motor y modelo.
- Reutilizar `Field`, `inputCls` y `btnPrimary` de `web/src/components.jsx`; sin estilos ni librerías nuevas.
- **Criterio:** `npm run build` en verde; la app recién clonada muestra catálogo y requisitos sin descargar nada.

## Paso 2.9 — Verificación y aceptación (P2-9)

- Tests: contrato de `transcript.json`; progreso 0-100; cancelación en todas las etapas; fallback sin diarización; recomendaciones por perfil; `/system` y `/api/catalog` sin importar librerías pesadas (test sobre `sys.modules`).
- Prueba manual documentada: app recién clonada → no se descarga ningún modelo; elegir un motor muestra sus requisitos; tras instalarlo la transcripción funciona sin tocar código; cambiar de motor no altera clips, revisión, acta ni informe.
- **Checklist de comparación para el usuario:** con un audio real en español, comparar a mano WhisperX + pyannote frente a Parakeet + Nemotron (calidad del texto, hablantes correctos, tiempo). El motor por defecto **no se cambia** hasta que el usuario lo decida con ese resultado.
- **Aceptación de la Fase 2:** app recién clonada sin modelos descargados; cada motor muestra sus requisitos; tras instalar un motor la transcripción funciona; cambiar de motor no afecta las demás etapas; tests (ejecutados por el usuario) y `npm run build` en verde.

---

## Diferido (fuera de la Fase 2)

- `faster-whisper`, Qwen3-ASR y FunASR: cada uno podría añadirse después como un único archivo de adaptador.
- `nemotron_hf.py` (variante GPU con Transformers/NeMo): puede entrar en conflicto de dependencias con WhisperX/torch; si se retoma, aislarlo en un entorno aparte.

## Riesgos propios de esta fase

- **CLI de NeMo-Speech.cpp:** el runtime es joven (v0.1.0) y los flags, la salida JSON y los GGUF multilingües no están verificados. Los pasos 2.5 y 2.6 tienen una verificación previa que detiene la tarea si no coinciden.
- **Calidad en español:** los benchmarks citados de Nemotron son sobre todo en inglés. Se valida a mano en 2.9.
- **Conflictos de dependencias:** WhisperX y los extras de NeMo pueden pelear por versiones de `torch`. Mientras los motores nuevos sean GGUF (binario externo) el riesgo es bajo.