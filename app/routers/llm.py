"""Endpoints para configuración y diagnóstico de proveedores LLM."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..services.llm.client import LlmClient, LlmError, PROVIDERS, list_models
from ..services.llm import prompts

router = APIRouter(tags=["llm"])


class LlmTestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


@router.get("/api/llm/models")
def get_models(provider: str = "ollama") -> dict:
    cfg = config.load_config()["llm"]
    provider_info = PROVIDERS.get(provider)
    if provider_info is None:
        raise HTTPException(400, f"Proveedor LLM desconocido: {provider}")
    base_url = cfg.get("base_url", "") if cfg.get("provider") == provider else ""
    api_key = cfg.get("api_key", "") if cfg.get("provider") == provider else ""
    return {"models": list_models(provider, base_url, api_key)}


@router.post("/api/llm/test")
def test_llm(payload: LlmTestRequest | None = None) -> dict:
    overrides = payload.model_dump(exclude_none=True) if payload else {}
    try:
        client = LlmClient(overrides=overrides)
        response = client.chat([{"role": "user", "content": "Responde únicamente: OK"}], max_tokens=16)
        return {"ok": True, "response": response}
    except LlmError:
        return {"ok": False, "error": "No se pudo probar el proveedor LLM; revisa la configuración y la conexión."}


@router.get("/api/prompts")
def get_prompts() -> dict:
    return {name: prompts.get_prompt(name) for name in prompts.DEFAULT_PROMPTS}


@router.put("/api/prompts")
def put_prompts(payload: dict[str, dict[str, str]]) -> dict:
    for name, value in payload.items():
        if name not in prompts.DEFAULT_PROMPTS:
            raise HTTPException(404, f"Prompt desconocido: {name}")
        try:
            prompts.validate(name, value.get("system", ""), value.get("user", ""))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    current = config.load_config().get("prompts", {})
    updated = {**current, **payload}
    config.save_config({"prompts": updated})
    return {name: prompts.get_prompt(name) for name in prompts.DEFAULT_PROMPTS}


@router.post("/api/prompts/{name}/reset")
def reset_prompt(name: str) -> dict:
    if name not in prompts.DEFAULT_PROMPTS:
        raise HTTPException(404, f"Prompt desconocido: {name}")
    current = config.load_config().get("prompts", {})
    current[name] = prompts.DEFAULT_PROMPTS[name].copy()
    config.save_config({"prompts": current})
    return {name: prompts.get_prompt(name)}
