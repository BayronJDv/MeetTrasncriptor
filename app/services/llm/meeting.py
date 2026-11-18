"""Análisis de la estructura de la reunión: temas, decisiones, votaciones, compromisos.

Proceso en dos fases: (1) resumen estructurado por ventanas, (2) consolidación.
El resultado es un esquema editable por el usuario antes del informe.
"""
from __future__ import annotations

import json

from ... import config
from ...jobs import Job
from ..llm.client import LlmClient, LlmError
from . import prompts
from .review import _window_payload, build_windows  # reutiliza agrupación y formato

PHASE1_PROMPT = """Resume esta parte de una reunión transcrita para identificar su estructura.
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
{segments}"""

PHASE2_PROMPT = """Consolida la estructura de una reunión a partir de resúmenes parciales.
Fusiona partes duplicadas o continuadas, ordena por tiempo y corrige límites solapados.

Resúmenes parciales (JSON):
{parts}

Devuelve EXCLUSIVAMENTE JSON válido:
{{"secciones": [{{"tipo": "tema|decision|votacion|compromiso|conclusion|otro",
  "titulo": "...", "inicio": <seg>, "fin": <seg>, "resumen": "...", "items": ["..."]}}]}}"""


def meeting_state(project_id: str) -> dict:
    return config.load_json(project_id, "meeting.json") or {"status": "idle", "sections": []}


def run_meeting_job(project_id: str, job: Job) -> None:
    from ...jobs import manager

    def _save_error(message: str) -> None:
        config.save_json(project_id, "meeting.json", {"status": "error", "error": message, "sections": []})

    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise RuntimeError("El proyecto no tiene transcripción")

    cfg = config.load_config()
    window_minutes = cfg["llm"].get("window_minutes", 10)
    speaker_names = {s["id"]: s.get("name") or s["id"] for s in transcript.get("speakers", [])}
    windows = build_windows(transcript, window_minutes)

    try:
        client = LlmClient(overrides="meeting_1")
        meeting_2_client = LlmClient(overrides="meeting_2")
    except LlmError as exc:
        _save_error(str(exc))
        raise

    all_parts: list[dict] = []
    for i, win in enumerate(windows):
        job.check_cancel()
        manager.update(
            job,
            stage=f"Analizando estructura ({i + 1}/{len(windows)})",
            progress=(i / len(windows)) * 80,
            detail=f"min {win[0]['start']/60:.0f}–{win[-1]['end']/60:.0f}",
        )
        prompt = prompts.render(
            "meeting_1",
            win_lo=win[0]["start"] / 60,
            win_hi=win[-1]["end"] / 60,
            segments=_window_payload(win, speaker_names),
        )["user"]
        try:
            data = client.chat_json(
                [
                    {"role": "system", "content": prompts.get_prompt("meeting_1_system")["system"]},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=3000,
            )
        except LlmError as exc:
            _save_error(str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            job.log_line(manager, f"Ventana {i + 1} omitida: {exc}")
            continue
        parts = data.get("partes") or []
        for p in parts:
            if isinstance(p, dict) and p.get("titulo"):
                p["_win_lo"] = win[0]["start"]
                p["_win_hi"] = win[-1]["end"]
                all_parts.append(p)

    manager.update(job, stage="Consolidando estructura", progress=85, detail=f"{len(all_parts)} partes parciales")

    compact = [
        {k: v for k, v in p.items() if not k.startswith("_")}
        for p in all_parts
    ]
    try:
        data = meeting_2_client.chat_json(
            [
                {"role": "system", "content": prompts.get_prompt("meeting_2_system")["system"]},
                {"role": "user", "content": prompts.render("meeting_2", parts=json.dumps(compact, ensure_ascii=False))["user"]},
            ],
            max_tokens=6000,
        )
        sections = data.get("secciones") or []
    except Exception as exc:  # noqa: BLE001
        job.log_line(manager, f"Consolidación falló ({exc}); se usan las partes sin fusionar")
        sections = compact

    if not sections:
        sections = compact

    out = []
    for idx, s in enumerate(sections):
        if not isinstance(s, dict) or not s.get("titulo"):
            continue
        tipo = s.get("tipo", "tema")
        if tipo not in ("tema", "decision", "votacion", "compromiso", "conclusion", "otro"):
            tipo = "otro"
        out.append(
            {
                "id": f"sec{idx + 1}",
                "type": tipo,
                "title": str(s["titulo"]),
                "start": _num(s.get("inicio")),
                "end": _num(s.get("fin")),
                "summary": str(s.get("resumen") or ""),
                "items": [str(i) for i in (s.get("items") or [])][:20],
            }
        )

    state = {"status": "done", "sections": out}
    config.save_json(project_id, "meeting.json", state)
    config.save_meta(project_id, {"has_meeting": True})
    job.log_line(manager, f"Estructura lista: {len(out)} secciones")


def _num(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None
