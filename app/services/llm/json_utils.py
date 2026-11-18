from __future__ import annotations

import json
import re
from typing import Any


class JsonParseError(ValueError):
    pass


class JsonResponseError(RuntimeError):
    pass


def extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?|```", "", text, flags=re.IGNORECASE).strip()
    cleaned = _remove_trailing_commas(cleaned)
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise JsonParseError("El modelo no devolvió un objeto JSON válido")


def _remove_trailing_commas(text: str) -> str:
    result = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
            result.append(character)
        elif character == ",":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if next_index < len(text) and text[next_index] in "}]":
                index += 1
                continue
            result.append(character)
        else:
            result.append(character)
        index += 1
    return "".join(result)


def chat_json_with_retry(
    client: Any,
    messages: list[dict],
    *,
    max_tokens: int,
    stage: str,
    required_key: str,
    required_value_type: type | None = None,
) -> dict[str, Any]:
    retry_instruction = (
        f"\n\nResponde solo con JSON válido e incluye la clave '{required_key}'. "
        "No incluyas texto ni formato Markdown."
    )
    for attempt in range(2):
        request_messages = messages
        if attempt:
            request_messages = [
                *messages[:-1],
                {**messages[-1], "content": messages[-1]["content"] + retry_instruction},
            ]
        try:
            data = client.chat_json(request_messages, max_tokens=max_tokens)
            if not isinstance(data, dict) or required_key not in data:
                raise JsonParseError(f"El objeto JSON no contiene la clave requerida '{required_key}'")
            if required_value_type is not None and not isinstance(data[required_key], required_value_type):
                raise JsonParseError(f"La clave '{required_key}' tiene un tipo inesperado")
            return data
        except JsonParseError as exc:
            if attempt:
                model = getattr(client, "model", "desconocido") or "desconocido"
                raise JsonResponseError(
                    f"Falló el parseo JSON en {stage} con el modelo {model} tras 2 intentos. "
                    "Prueba un modelo más grande o revisa el prompt."
                ) from exc
    raise AssertionError("flujo de reintentos inalcanzable")
