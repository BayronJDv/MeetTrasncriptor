"""Generación del informe final en dos fases (soporta transcripciones de 3 h).

Fase 1 (map): resumen detallado por ventanas con hablantes y tiempos.
Fase 2 (reduce): redacción del informe siguiendo la plantilla del usuario.
Reanudable: las ventanas ya resumidas se guardan en report_work.json.
"""
from __future__ import annotations

import hashlib
import json

from ... import config
from ...jobs import Job
from ..llm.client import LlmClient
from . import json_utils, prompts
from .review import _window_payload, build_windows

PHASE1_PROMPT = """Genera notas detalladas de esta parte de una reunión para redactar un acta.
Incluye: temas tratados en orden, quién dijo qué (usando los nombres reales de los hablantes),
decisiones, votos, cifras y compromisos con sus tiempos aproximados (segundos).
Sé exhaustivo pero conciso. Español. Lista con viñetas.
Devuelve únicamente un objeto JSON válido con esta forma: {{"notes": "texto de las notas"}}.

Transcripción (min {win_lo}–{win_hi}):
{segments}"""

PHASE2_PROMPT = """Redacta el INFORME FINAL en Markdown a partir de las notas de una reunión.

{template_block}{meeting_block}
Notas cronológicas de la reunión:
{notes}

{instructions_block}
Requisitos:
- Estructura el informe siguiendo EXACTAMENTE las secciones de la plantilla (si hay).
- Usa los nombres reales de los hablantes, no SPEAKER_XX.
- Cita tiempos aproximados cuando aporten (formato mm:ss).
- No inventes información que no esté en las notas.
- Devuelve únicamente un objeto JSON válido con esta forma: {{"markdown": "informe completo en Markdown"}}."""


def read_template(name: str) -> str:
    """Lee una plantilla (md/txt/docx) y devuelve su contenido textual."""
    from ...config import TEMPLATES_DIR

    path = TEMPLATES_DIR / name
    if not path.exists():
        raise RuntimeError(f"Plantilla no encontrada: {name}")
    if path.suffix.lower() == ".docx":
        from ..export import docx_to_text

        return docx_to_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _hash_window(segments: list[dict]) -> str:
    payload = json.dumps([[s["id"], s["text"]] for s in segments], ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def run_report_job(
    project_id: str,
    job: Job,
    template_name: str | None,
    instructions: str,
    include_meeting: bool = True,
) -> None:
    from ...jobs import manager

    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise RuntimeError("El proyecto no tiene transcripción")

    cfg = config.load_config()
    advanced = cfg["advanced"]
    client = LlmClient(overrides="report_1")
    report_2_client = LlmClient(overrides="report_2")
    speaker_names = {s["id"]: (s.get("name") or s["id"]) for s in transcript.get("speakers", [])}
    windows = build_windows(transcript, max(10, cfg["llm"].get("window_minutes", 10) * 1.5))

    work = config.load_json(project_id, "report_work.json") or {"notes": [], "processed": []}

    # ---- fase 1: notas por ventana ----
    for i, win in enumerate(windows):
        job.check_cancel()
        h = _hash_window(win)
        if h in work["processed"]:
            continue
        manager.update(
            job,
            stage=f"Resumiendo tramos ({i + 1}/{len(windows)})",
            progress=(i / len(windows)) * 60,
            detail=f"min {win[0]['start']/60:.0f}–{win[-1]['end']/60:.0f}",
        )
        prompt = prompts.render(
            "report_1",
            win_lo=win[0]["start"] / 60,
            win_hi=win[-1]["end"] / 60,
            segments=_window_payload(win, speaker_names),
        )["user"]
        try:
            response = json_utils.chat_json_with_retry(
                client,
                [
                    {"role": "system", "content": prompts.get_prompt("report_1_system")["system"]},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=3500,
                stage=f"generación de notas del informe, tramo {i + 1}",
                required_key="notes",
                required_value_type=str,
            )
            notes = response["notes"]
        except json_utils.JsonResponseError:
            raise
        except Exception as exc:  # noqa: BLE001
            job.log_line(manager, f"Tramo {i + 1} omitido: {exc}")
            continue
        work["notes"].append({"window": i, "start": win[0]["start"], "end": win[-1]["end"], "notes": notes})
        work["processed"].append(h)
        config.save_json(project_id, "report_work.json", work)

    if not work["notes"]:
        raise RuntimeError("No se pudo generar ningún resumen de la transcripción")

    # ---- fase 2: informe final ----
    manager.update(job, stage="Redactando informe", progress=70, detail="Sección por sección…")
    template_block = ""
    if template_name:
        template_text = read_template(template_name).strip()
        if template_text:
            template_block = f"PLANTILLA DEL INFORME (estructura y secciones a respetar):\n\n---\n{template_text[:advanced.get('report_template_max_chars', 12000)]}\n---\n\n"
    meeting_block = ""
    if include_meeting:
        meeting = config.load_json(project_id, "meeting.json") or {}
        sections = meeting.get("sections") or []
        if sections:
            outline = json.dumps(sections, ensure_ascii=False, indent=1)
            meeting_block = f"ESTRUCTURA DETECTADA DE LA REUNIÓN (útil como guía):\n{outline[:advanced.get('report_meeting_max_chars', 6000)]}\n\n"
    instructions_block = ""
    if instructions.strip():
        instructions_block = f"INDICACIONES ADICIONALES DEL USUARIO:\n{instructions.strip()[:advanced.get('report_instructions_max_chars', 4000)]}\n"

    notes_text = "\n\n".join(
        f"[min {n['start']/60:.0f}–{n['end']/60:.0f}]\n{n['notes']}" for n in work["notes"]
    )
    response = json_utils.chat_json_with_retry(
        report_2_client,
        [
            {"role": "system", "content": prompts.get_prompt("report_2_system")["system"]},
            {"role": "user", "content": prompts.render(
                "report_2",
                template_block=template_block,
                meeting_block=meeting_block,
                notes=notes_text[:advanced.get('report_notes_max_chars', 120000)],
                instructions_block=instructions_block,
            )["user"]},
        ],
        max_tokens=8000,
        stage="redacción del informe final",
        required_key="markdown",
        required_value_type=str,
    )
    markdown = response["markdown"]

    config.save_json(project_id, "informe.md.json", {"markdown": markdown})
    (config.project_dir(project_id) / "informe.md").write_text(markdown, encoding="utf-8")
    config.save_meta(project_id, {"has_report": True, "report_template": template_name})
    manager.update(job, stage="Informe listo", progress=100, detail=f"{len(markdown)} caracteres")
    job.log_line(manager, "Informe generado")
