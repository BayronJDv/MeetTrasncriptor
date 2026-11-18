from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..jobs import manager
from ..services import catalog

router = APIRouter(prefix="/api", tags=["catalog"])


class InstallRequest(BaseModel):
    terms_confirmation: str | None = None


@router.get("/catalog")
def list_catalog() -> list[dict]:
    return catalog.get_catalog()


@router.post("/engines/{engine_id}/install")
def install_engine(engine_id: str, body: InstallRequest | None = None) -> dict:
    engine = catalog.get_engine(engine_id)
    if engine is None:
        raise HTTPException(404, "Motor desconocido")
    if engine_id not in catalog.INSTALL_EXTRAS:
        raise HTTPException(409, "Este motor requiere instalación manual")
    if engine_id == "pyannote":
        if not catalog.has_hf_token():
            raise HTTPException(400, "Configura tu token de Hugging Face antes de continuar")
        if body is None or body.terms_confirmation != "Acepto los términos":
            raise HTTPException(400, "Confirma los términos escribiendo: Acepto los términos")
        catalog.accept_pyannote_terms()

    def run(job) -> None:
        job.stage = "install"
        job.progress = 5.0
        job.detail = f"Instalando {engine['label']}"
        manager.update(job)
        catalog.install_extra(engine_id, check_cancel=job.check_cancel)

    try:
        job = manager.submit("engine_install", "__system__", run)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job.snapshot()
