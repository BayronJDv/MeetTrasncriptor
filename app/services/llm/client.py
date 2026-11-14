"""Cliente LLM unificado vía API compatible con OpenAI.

Soporta: groq, gemini (endpoint OpenAI-compat), openrouter, ollama y personalizado.
Reintentos con backoff exponencial para respetar límites del plan gratuito.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from ... import config

PROVIDERS: dict[str, dict[str, Any]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "allam-2-7b",
        ],
        "needs_key": True,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"],
        "needs_key": True,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-2.5-72b-instruct:free",
        ],
        "needs_key": True,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.1", "qwen2.5", "mistral"],
        "needs_key": False,
    },
    "custom": {"base_url": "", "models": [], "needs_key": False},
}


class LlmError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, overrides: dict | None = None) -> None:
        cfg = config.load_config()["llm"]
        if overrides:
            cfg = {**cfg, **overrides}
        self.provider = cfg["provider"]
        self.model = cfg["model"]
        self.api_key = cfg.get("api_key", "")
        self.temperature = cfg.get("temperature", 0.2)
        self.max_retries = cfg.get("max_retries", 4)
        self.base_url = cfg.get("base_url") or PROVIDERS[self.provider]["base_url"]
        if not self.base_url:
            raise LlmError("Falta la URL base del proveedor personalizado (Ajustes → IA)")
        if PROVIDERS[self.provider]["needs_key"] and not self.api_key:
            raise LlmError(f"Falta la API key de {self.provider} (Ajustes → IA)")

    def chat(self, messages: list[dict], max_tokens: int = 4096, json_mode: bool = False) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "Transcriptor de reuniones"

        delay = 2.0
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=180) as client:
                    resp = client.post(
                        f"{self.base_url.rstrip('/')}/chat/completions",
                        json=body,
                        headers=headers,
                    )
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        delay = min(delay * 2, 60)
                        continue
                    raise LlmError(f"El proveedor falló tras {self.max_retries + 1} intentos: {last_error}")
                if resp.status_code >= 400:
                    raise LlmError(f"HTTP {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content or ""
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                raise LlmError(f"Sin conexión con {self.provider}: {last_error}") from exc
        raise LlmError(last_error or "Error desconocido del proveedor")

    def chat_json(self, messages: list[dict], max_tokens: int = 4096) -> Any:
        """Chat esperando JSON de respuesta, con limpieza robusta."""
        text = self.chat(messages, max_tokens=max_tokens, json_mode=True)
        return extract_json(text)


def extract_json(text: str) -> Any:
    """Extrae el primer objeto/array JSON de una respuesta (tolera ```json y texto extra)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # buscar el bloque balanceado más externo
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start: i + 1])
                    except json.JSONDecodeError:
                        break
    raise LlmError(f"El modelo no devolvió JSON válido:\n{text[:400]}")
