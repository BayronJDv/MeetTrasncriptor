from __future__ import annotations

from typing import Any

from ... import config

DEFAULT_PROMPTS: dict[str, dict[str, str]] = {
    "review_system": {
        "system": (
            "Eres un revisor experto de transcripciones automáticas (ASR) de reuniones en español. "
            "Recibes una lista de segmentos con id, hablante y texto. Detecta ÚNICAMENTE fragmentos con "
            "errores evidentes de reconocimiento de voz: palabras sin sentido, deformaciones fonéticas "
            "(p. ej. 'conduci mi barro' cuando el contexto sugiere otra cosa), repeticiones corruptas, "
            "nombres propios mal transcritos de forma evidente, o frases semánticamente incoherentes con "
            "el contexto de una reunión. NO corrijas estilo ni puntuación. NO inventes contenido: si no "
            "hay errores claros, devuelve una lista vacía."
        ),
        "user": "",
    },
    "review_user": {
        "system": "",
        "user": """Segmentos de la transcripción (los tiempos son segundos desde el inicio):

{segments}

Devuelve EXCLUSIVAMENTE un JSON válido con esta forma:
{{"sugerencias": [{{"ids": [<ids de segmentos afectados>], "original": "<texto problemático literal>", "sugerencia": "<corrección propuesta>", "motivo": "<por qué parece un error de transcripción>"}}]}}

Reglas:
- Los ids deben existir en la lista anterior.
- "original" debe ser una cita literal del texto (una frase o palabra), no un resumen.
- Máximo {max_suggestions} sugerencias; prioriza las más claras.
- Si todo se ve coherente, devuelve {{"sugerencias": []}}.""",
    },
    "meeting_1_system": {
        "system": "Eres un analista experto en actas de reunión. Respondes solo JSON válido en español.",
        "user": "",
    },
    "meeting_1": {
        "system": "",
        "user": """Resume esta parte de una reunión transcrita para identificar su estructura.
Devuelve EXCLUSIVAMENTE JSON válido:
{{"partes": [{{"tipo": "tema|decision|votacion|compromiso|conclusion|otro",
  "titulo": "<título breve>",
  "inicio": <segundo aprox. de inicio>, "fin": <segundo aprox. de fin>,
  "resumen": "<2-4 frases>",
  "items": ["<punto concreto, voto, acuerdo o compromisos con responsable si consta>"]}}]}}

Detecta especialmente: cambio de tema del orden del día, decisiones adoptadas,
VOTACIONES (quién propuso, a favor/en contra/abstenciones si consta), compromisos
(quién hará qué) y conclusiones finales. Todo en español. Los tiempos deben
corresponder a los segundos reales que aparecen abajo.

Transcripción (min {win_lo}–{win_hi}):
{segments}""",
    },
    "meeting_2_system": {
        "system": "Eres un analista experto en actas de reunión. Respondes solo JSON válido en español.",
        "user": "",
    },
    "meeting_2": {
        "system": "",
        "user": """Consolida la estructura de una reunión a partir de resúmenes parciales.
Fusiona partes duplicadas o continuadas, ordena por tiempo y corrige límites solapados.

Resúmenes parciales (JSON):
{parts}

Devuelve EXCLUSIVAMENTE JSON válido:
{{"secciones": [{{"tipo": "tema|decision|votacion|compromiso|conclusion|otro",
  "titulo": "...", "inicio": <seg>, "fin": <seg>, "resumen": "...", "items": ["..."]}}]}}""",
    },
    "report_1_system": {
        "system": "Eres un secretário de actas meticuloso. Trabajas en español.",
        "user": "",
    },
    "report_1": {
        "system": "",
        "user": """Genera notas detalladas de esta parte de una reunión para redactar un acta.
Incluye: temas tratados en orden, quién dijo qué (usando los nombres reales de los hablantes),
decisiones, votos, cifras y compromisos con sus tiempos aproximados (segundos).
Sé exhaustivo pero conciso. Español. Lista con viñetas.

Transcripción (min {win_lo}–{win_hi}):
{segments}""",
    },
    "report_2_system": {
        "system": "Eres un redactor profesional de informes y actas de reunión en español. Escribe claro, formal y fiel a los datos.",
        "user": "",
    },
    "report_2": {
        "system": "",
        "user": """Redacta el INFORME FINAL en Markdown a partir de las notas de una reunión.

{template_block}{meeting_block}
Notas cronológicas de la reunión:
{notes}

{instructions_block}
Requisitos:
- Estructura el informe siguiendo EXACTAMENTE las secciones de la plantilla (si hay).
- Usa los nombres reales de los hablantes, no SPEAKER_XX.
- Cita tiempos aproximados cuando aporten (formato mm:ss).
- No inventes información que no esté en las notas.
- Devuelve SOLO el contenido del informe en Markdown, sin explicaciones.""",
    },
}

REQUIRED_VARS: dict[str, set[str]] = {
    "review_system": set(),
    "review_user": {"segments", "max_suggestions"},
    "meeting_1_system": set(),
    "meeting_1": {"win_lo", "win_hi", "segments"},
    "meeting_2_system": set(),
    "meeting_2": {"parts"},
    "report_1_system": set(),
    "report_1": {"win_lo", "win_hi", "segments"},
    "report_2_system": set(),
    "report_2": {"template_block", "meeting_block", "notes", "instructions_block"},
}

MAX_PROMPT_LENGTH = 120_000


def get_prompt(name: str) -> dict[str, str]:
    if name not in DEFAULT_PROMPTS:
        raise KeyError(f"Prompt desconocido: {name}")
    stored = config.load_config().get("prompts", {}).get(name, {})
    default = DEFAULT_PROMPTS[name]
    return {
        part: stored.get(part) or default[part]
        for part in ("system", "user")
    }


def render(name: str, **vars: Any) -> dict[str, str]:
    prompt = get_prompt(name)
    rendered = {}
    for part, text in prompt.items():
        replacements = {}
        for index, (key, value) in enumerate(vars.items()):
            marker = f"__PROMPT_VALUE_{index}__"
            text = text.replace("{{" + key.upper() + "}}", marker)
            text = text.replace("{" + key + "}", marker)
            replacements[marker] = str(value)
        text = text.replace("{{", "{").replace("}}", "}")
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        rendered[part] = text
    return rendered


def validate(name: str, system: str, user: str) -> None:
    if name not in REQUIRED_VARS:
        raise KeyError(f"Prompt desconocido: {name}")
    if not isinstance(system, str) or not isinstance(user, str):
        raise ValueError("Los prompts system y user deben ser texto")
    if len(system) > MAX_PROMPT_LENGTH or len(user) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Los prompts no pueden superar {MAX_PROMPT_LENGTH} caracteres")
    combined = system + "\n" + user
    missing = {
        variable
        for variable in REQUIRED_VARS[name]
        if "{{" + variable.upper() + "}}" not in combined
        and "{" + variable + "}" not in combined
    }
    if missing:
        raise ValueError(f"Faltan variables requeridas para {name}: {', '.join(sorted(missing))}")
