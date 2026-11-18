"""Revisión asistida por IA: detección de fragmentos con errores evidentes de ASR.

Ejemplo: "conduci mi barro" → el LLM sugiere que es incoherente y propone corrección.
El usuario escucha el fragmento y acepta/edita/rechaza. Progreso persistente (reanudable).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ... import config
from ...jobs import Job, JobCancelled
from ..llm.client import LlmClient, LlmError
from . import json_utils, prompts

SYSTEM_PROMPT = (
    "Eres un revisor experto de transcripciones automáticas (ASR) de reuniones en español. "
    "Recibes una lista de segmentos con id, hablante y texto. Detecta ÚNICAMENTE fragmentos con "
    "errores evidentes de reconocimiento de voz: palabras sin sentido, deformaciones fonéticas "
    "(p. ej. 'conduci mi barro' cuando el contexto sugiere otra cosa), repeticiones corruptas, "
    "nombres propios mal transcritos de forma evidente, o frases semánticamente incoherentes con "
    "el contexto de una reunión. NO corrijas estilo ni puntuación. NO inventes contenido: si no "
    "hay errores claros, devuelve una lista vacía."
)

USER_TEMPLATE = """Segmentos de la transcripción (los tiempos son segundos desde el inicio):

{segments}

Devuelve EXCLUSIVAMENTE un JSON válido con esta forma:
{{"sugerencias": [{{"ids": [<ids de segmentos afectados>], "original": "<texto problemático literal>", "sugerencia": "<corrección propuesta>", "motivo": "<por qué parece un error de transcripción>"}}]}}

Reglas:
- Los ids deben existir en la lista anterior.
- "original" debe ser una cita literal del texto (una frase o palabra), no un resumen.
- Máximo {max_suggestions} sugerencias; prioriza las más claras.
- Si todo se ve coherente, devuelve {{"sugerencias": []}}."""


def build_windows(transcript: dict, window_minutes: float) -> list[list[dict]]:
    """Agrupa segmentos en ventanas temporales consecutivas."""
    if not transcript or not transcript.get("segments"):
        return []
    limit = window_minutes * 60
    windows: list[list[dict]] = []
    current: list[dict] = []
    win_start = transcript["segments"][0]["start"]
    for seg in transcript["segments"]:
        if current and seg["start"] - win_start >= limit:
            windows.append(current)
            current = []
            win_start = seg["start"]
        current.append(seg)
    if current:
        windows.append(current)
    return windows


def _window_hash(segments: list[dict]) -> str:
    payload = json.dumps([[s["id"], s["text"]] for s in segments], ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _window_payload(segments: list[dict], speaker_names: dict[str, str]) -> str:
    lines = []
    for s in segments:
        speaker = speaker_names.get(s.get("speaker") or "", s.get("speaker") or "?")
        lines.append(json.dumps({"id": s["id"], "hablante": speaker, "texto": s["text"]}, ensure_ascii=False))
    return "\n".join(lines)


def _valid_original(original: str, segments: list[dict]) -> bool:
    """Guardia contra alucinaciones: el texto citado debe parecerse al real."""
    if not original:
        return False
    joined = " ".join(s["text"] for s in segments).lower()
    tokens = [t for t in original.lower().split() if len(t) > 2]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in joined)
    return hits / len(tokens) >= 0.5


def review_suggestion_state(project_id: str) -> dict:
    state = config.load_json(project_id, "review.json") or {
        "status": "idle",
        "suggestions": [],
        "processed_windows": [],
    }
    return state


def accept_suggestion(project_id: str, suggestion_id: str, replacement: str | None) -> dict:
    """Acepta una sugerencia: aplica el texto corregido a la transcripción."""
    state = review_suggestion_state(project_id)
    transcript = config.load_json(project_id, "transcript.json")
    if not transcript:
        raise RuntimeError("No hay transcripción")
    sug = next((s for s in state["suggestions"] if s["id"] == suggestion_id), None)
    if not sug:
        raise RuntimeError("Sugerencia no encontrada")
    final_text = (replacement if replacement is not None else sug["suggestion"]).strip()
    by_id = {s["id"]: s for s in transcript["segments"]}
    for sid in sug["ids"]:
        seg = by_id.get(sid)
        if not seg:
            continue
        if seg.get("original_text") is None:
            seg["original_text"] = seg["text"]
        seg["text"] = final_text if len(sug["ids"]) == 1 else seg["text"]
        seg["edited"] = True
    if len(sug["ids"]) == 1:
        by_id[sug["ids"][0]]["text"] = final_text
    sug["status"] = "accepted" if replacement is None else "edited"
    sug["replacement"] = final_text
    config.save_json(project_id, "review.json", state)
    config.save_json(project_id, "transcript.json", transcript)
    return sug


def reject_suggestion(project_id: str, suggestion_id: str) -> dict:
    state = review_suggestion_state(project_id)
    sug = next((s for s in state["suggestions"] if s["id"] == suggestion_id), None)
    if not sug:
        raise RuntimeError("Sugerencia no encontrada")
    sug["status"] = "rejected"
    config.save_json(project_id, "review.json", state)
    return sug


def run_review_job(project_id: str, job: Job) -> None:
    from ...jobs import manager

    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise RuntimeError("El proyecto no tiene transcripción para revisar")

    cfg = config.load_config()
    window_minutes = cfg["llm"].get("window_minutes", 10)
    concurrency = max(1, min(4, cfg["llm"].get("concurrency", 2)))
    max_suggestions = cfg["advanced"].get("max_suggestions", 10)

    state = review_suggestion_state(project_id)
    state["status"] = "running"
    state.setdefault("processed_windows", [])
    state.setdefault("suggestions", [])

    windows = build_windows(transcript, window_minutes)
    speaker_names = {s["id"]: s.get("name") or s["id"] for s in transcript.get("speakers", [])}
    pending = []
    for win in windows:
        h = _window_hash(win)
        if h not in state["processed_windows"]:
            pending.append((h, win))
    job.log_line(manager, f"{len(windows)} ventanas; {len(pending)} pendientes (reanudable)")

    if not pending:
        state["status"] = "done"
        config.save_json(project_id, "review.json", state)
        manager.update(job, stage="Revisión completada", progress=100, detail="Sin ventanas pendientes")
        return

    try:
        client = LlmClient(overrides="review")
    except LlmError as exc:
        state["status"] = "error"
        state["error"] = str(exc)
        config.save_json(project_id, "review.json", state)
        raise
    done_count = 0
    provider_errors: list[str] = []
    json_errors: list[str] = []

    def process_window(item: tuple[str, list[dict]]) -> None:
        nonlocal done_count
        h, win = item
        if job.cancel_event.is_set():
            raise JobCancelled()
        prompt = prompts.render(
            "review_user",
            segments=_window_payload(win, speaker_names),
            max_suggestions=max_suggestions,
        )["user"]
        try:
            data = json_utils.chat_json_with_retry(
                client,
                [
                    {"role": "system", "content": prompts.get_prompt("review_system")["system"]},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                stage="revisión de transcripción",
                required_key="sugerencias",
            )
        except json_utils.JsonResponseError as exc:
            json_errors.append(str(exc))
            job.log_line(manager, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            if not provider_errors:
                provider_errors.append(f"{type(exc).__name__}: {exc}")
            job.log_line(manager, f"Ventana omitida por error del proveedor: {exc}")
            return

        seg_ids = {s["id"] for s in win}
        seen: set[tuple] = set()
        for sug in (data.get("sugerencias") or data.get("suggestions") or []):
            if not isinstance(sug, dict):
                continue
            ids = [i for i in (sug.get("ids") or []) if i in seg_ids]
            original = str(sug.get("original") or "").strip()
            if not ids or not _valid_original(original, win):
                continue
            key = tuple(sorted(ids)) + (original[:80],)
            if key in seen:
                continue
            seen.add(key)
            starts = [by_id["start"] for by_id in win if by_id["id"] in ids]
            ends = [by_id["end"] for by_id in win if by_id["id"] in ids]
            state["suggestions"].append(
                {
                    "id": uuid.uuid4().hex[:10],
                    "ids": ids,
                    "start": min(starts),
                    "end": max(ends),
                    "original": original,
                    "suggestion": str(sug.get("sugerencia") or sug.get("suggestion") or "").strip(),
                    "reason": str(sug.get("motivo") or sug.get("reason") or "").strip(),
                    "status": "pending",
                    "replacement": None,
                }
            )
        state["processed_windows"].append(h)
        done_count += 1
        config.save_json(project_id, "review.json", state)
        manager.update(
            job,
            stage=f"Revisando IA ({done_count}/{len(pending)})",
            progress=done_count / len(pending) * 100,
            detail=f"min {win[0]['start']/60:.0f}–{win[-1]['end']/60:.0f} · {len(state['suggestions'])} sugerencias",
        )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(process_window, item) for item in pending]
        for f in as_completed(futures):
            f.result()

    if json_errors:
        state["status"] = "error"
        state["error"] = json_errors[0]
        config.save_json(project_id, "review.json", state)
        raise RuntimeError(state["error"])

    if pending and done_count == 0 and provider_errors:
        state["status"] = "error"
        state["error"] = (
            f"Todas las ventanas fallaron al contactar con el proveedor IA. "
            f"Primer error: {provider_errors[0]}"
        )
        config.save_json(project_id, "review.json", state)
        raise RuntimeError(state["error"])

    state["status"] = "done"
    config.save_json(project_id, "review.json", state)
    job.log_line(manager, f"Revisión terminada: {len(state['suggestions'])} sugerencias")
