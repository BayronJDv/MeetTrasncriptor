"""Exportación: Markdown → DOCX (python-docx) y extracción de texto desde DOCX."""
from __future__ import annotations

import re
from pathlib import Path


def docx_to_text(path: Path) -> str:
    """Extrae el texto de un .docx conservando encabezados y listas en Markdown."""
    from docx import Document

    doc = Document(str(path))
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if "heading 1" in style or "título 1" in style:
            lines.append(f"# {text}")
        elif "heading 2" in style or "título 2" in style:
            lines.append(f"## {text}")
        elif "heading 3" in style or "título 3" in style:
            lines.append(f"### {text}")
        elif "list" in style:
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")


def _add_runs(paragraph, text: str) -> None:
    """Añade texto con soporte de **negrita** y *cursiva*."""
    pos = 0
    tokens = []
    for m in re.finditer(r"\*\*(.+?)\*\*|(?<!\*)\*([^*]+?)\*(?!\*)", text):
        if m.start() > pos:
            tokens.append(("plain", text[pos:m.start()]))
        if m.group(1) is not None:
            tokens.append(("bold", m.group(1)))
        else:
            tokens.append(("italic", m.group(2)))
        pos = m.end()
    if pos < len(text):
        tokens.append(("plain", text[pos:]))
    for kind, value in tokens:
        run = paragraph.add_run(value)
        if kind == "bold":
            run.bold = True
        elif kind == "italic":
            run.italic = True


def markdown_to_docx(markdown: str, out_path: Path) -> None:
    """Convierte un informe Markdown a DOCX (encabezados, listas, negritas)."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("####"):
            p = doc.add_heading(level=4)
            _add_runs(p, line.lstrip("#").strip())
        elif line.startswith("###"):
            p = doc.add_heading(level=3)
            _add_runs(p, line.lstrip("#").strip())
        elif line.startswith("##"):
            p = doc.add_heading(level=2)
            _add_runs(p, line.lstrip("#").strip())
        elif line.startswith("#"):
            p = doc.add_heading(level=1)
            _add_runs(p, line.lstrip("#").strip())
        elif re.match(r"^\s*[-*]\s+", line):
            p = doc.add_paragraph(style="List Bullet")
            _add_runs(p, re.sub(r"^\s*[-*]\s+", "", line))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            p = doc.add_paragraph(style="List Number")
            _add_runs(p, re.sub(r"^\s*\d+[.)]\s+", "", line))
        elif line.strip().startswith("---") and len(line.strip()) <= 3:
            continue
        else:
            p = doc.add_paragraph()
            _add_runs(p, line.strip())

    doc.save(str(out_path))
