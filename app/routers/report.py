"""Informe: plantillas, generación con IA, edición y exportación (docx/md)."""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from .. import config
from ..config import TEMPLATES_DIR
from ..jobs import manager
from ..schemas import ReportGenerate, ReportSave
from ..services.export import markdown_to_docx
from ..services.llm.report import read_template, run_report_job

router = APIRouter(prefix="/api", tags=["report"])

TEMPLATE_EXT = {".md", ".txt", ".docx"}


def _safe_template_name(name: str) -> str:
    name = re.sub(r"[^\w\s.\-()áéíóúÁÉÍÓÚñÑ]", "_", name).strip()
    if not name or name.startswith("."):
        raise HTTPException(400, "Nombre de plantilla inválido")
    if "." + name.rsplit(".", 1)[-1].lower() not in TEMPLATE_EXT:
        raise HTTPException(400, f"Formato permitido: {', '.join(sorted(TEMPLATE_EXT))}")
    return name[:100]


@router.get("/templates")
def list_templates() -> list[dict]:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return [
        {"name": f.name, "size": f.stat().st_size, "modified": time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime))}
        for f in sorted(TEMPLATES_DIR.iterdir())
        if f.suffix.lower() in TEMPLATE_EXT
    ]


@router.post("/templates")
async def upload_template(file: UploadFile = File(...)) -> dict:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_template_name(file.filename or "plantilla.md")
    dest = TEMPLATES_DIR / name
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Plantilla demasiado grande (máx. 20 MB)")
    dest.write_bytes(content)
    return {"name": name}


@router.delete("/templates")
def delete_template(name: str) -> dict:
    path = TEMPLATES_DIR / _safe_template_name(name)
    if not path.exists():
        raise HTTPException(404, "Plantilla no encontrada")
    path.unlink()
    return {"ok": True}


@router.get("/templates/content")
def template_content(name: str) -> PlainTextResponse:
    path = TEMPLATES_DIR / _safe_template_name(name)
    if not path.exists():
        raise HTTPException(404, "Plantilla no encontrada")
    return PlainTextResponse(read_template(path.name))


@router.post("/projects/{project_id}/report/generate")
def generate_report(project_id: str, body: ReportGenerate) -> dict:
    transcript = config.load_json(project_id, "transcript.json")
    if not transcript or not transcript.get("segments"):
        raise HTTPException(400, "El proyecto no tiene transcripción")

    def run(job) -> None:
        run_report_job(project_id, job, body.template_name, body.instructions, body.include_meeting)

    job = manager.submit("report", project_id, run)
    return job.snapshot()


@router.get("/projects/{project_id}/report")
def get_report(project_id: str) -> dict:
    path = config.PROJECTS_DIR / project_id / "informe.md"
    if not path.exists():
        raise HTTPException(404, "Aún no hay informe")
    return {
        "markdown": path.read_text(encoding="utf-8", errors="replace"),
        "template": (config.load_meta(project_id) or {}).get("report_template"),
    }


@router.put("/projects/{project_id}/report")
def save_report(project_id: str, body: ReportSave) -> dict:
    path = config.PROJECTS_DIR / project_id / "informe.md"
    path.write_text(body.markdown, encoding="utf-8")
    config.save_json(project_id, "informe.md.json", {"markdown": body.markdown})
    return {"ok": True}


@router.get("/projects/{project_id}/report/export")
def export_report(project_id: str, format: str = "docx") -> FileResponse:
    path = config.PROJECTS_DIR / project_id / "informe.md"
    if not path.exists():
        raise HTTPException(404, "Aún no hay informe")
    meta = config.load_meta(project_id) or {}
    base = f"informe_{meta.get('name', project_id)}"
    markdown = path.read_text(encoding="utf-8", errors="replace")
    if format == "md":
        return FileResponse(path, media_type="text/markdown", filename=f"{base}.md")
    out = config.PROJECTS_DIR / project_id / f"{base}.docx"
    markdown_to_docx(markdown, out)
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{base}.docx",
    )
