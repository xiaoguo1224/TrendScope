from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.models.configuration import AIProviderConfig


ProviderRoute = Literal["openai_responses", "openai_chat", "anthropic_messages", "gemini", "ollama_generate", "ollama_chat"]


class OpenAICompatibleProvider:
    """URL-routed client for OpenAI-compatible, Anthropic, Gemini and Ollama APIs.

    The URL is the contract: complete paths such as ``/v1/messages`` or
    ``:generateContent`` choose the matching wire format. A plain base URL keeps
    a safe OpenAI-compatible fallback for services that expose only ``/v1``.
    """

    def __init__(self, config: AIProviderConfig) -> None:
        if not config.base_url or not config.model_name:
            raise ValueError(f"Enabled {config.provider_type} provider '{config.name}' requires a Base URL and model name")
        _validate_http_url(config.base_url)
        self.name = config.name
        self.model_name = config.model_name
        self.api_key = config.api_key or ""
        self.base_url = config.base_url
        self.timeout_seconds = config.timeout_seconds or 60
        self.max_retries = config.max_retries if config.max_retries is not None else 2
        self.last_endpoint = config.base_url

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = "Return exactly one JSON object. Do not use Markdown fences or add commentary."
        user = f"{prompt}\n\nContext JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        return _json_object(await self._request(system=system, user=user))

    async def analyze_image(self, *, image_path: Path, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        return await self.analyze_image_bytes(
            image_bytes=image_path.read_bytes(), mime_type=mime_type, prompt=prompt, context=context,
        )

    async def analyze_image_bytes(self, *, image_bytes: bytes, mime_type: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = "Return exactly one JSON object. Do not use Markdown fences or add commentary."
        user = f"{prompt}\n\nContext JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        return _json_object(await self._request(
            system=system,
            user=user,
            image_data=base64.b64encode(image_bytes).decode("ascii"),
            mime_type=mime_type,
        ))

    async def _request(self, *, system: str, user: str, image_data: str | None = None, mime_type: str | None = None) -> str:
        last_error: Exception | None = None
        for route in _routes_to_try(self.base_url, self.model_name):
            endpoint = _endpoint_for(self.base_url, route)
            payload = _payload_for(route, self.model_name, system, user, image_data, mime_type)
            headers = _headers_for(route, self.api_key)
            for attempt in range(self.max_retries + 1):
                try:
                    response = await asyncio.to_thread(self._post, endpoint, payload, headers)
                    self.last_endpoint = endpoint
                    return _response_text(response, route)
                except Exception as error:
                    last_error = error
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
            # An explicit endpoint must never be silently redirected to another API.
            if _has_explicit_route(self.base_url) or "protocol_not_supported" not in str(last_error):
                break
        raise RuntimeError(f"AI provider '{self.name}' request failed: {_safe_error(last_error)}") from last_error

    def _post(self, endpoint: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is an explicit user-owned provider config
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Network error: {error.reason}") from error
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("Provider returned invalid JSON") from error
        if not isinstance(parsed, dict):
            raise RuntimeError("Provider returned an invalid response object")
        return parsed


def _validate_http_url(value: str) -> None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AI provider Base URL must be an HTTP(S) URL")


def _routes_to_try(base_url: str, model_name: str) -> list[ProviderRoute]:
    value = base_url.rstrip("/").lower()
    if value.endswith("/messages"):
        return ["anthropic_messages"]
    if ":generatecontent" in value:
        return ["gemini"]
    if value.endswith("/api/generate"):
        return ["ollama_generate"]
    if value.endswith("/api/chat"):
        return ["ollama_chat"]
    if value.endswith("/responses"):
        return ["openai_responses"]
    if value.endswith("/chat") or value.endswith("/chat/completions"):
        return ["openai_chat"]
    primary: ProviderRoute = "openai_responses" if model_name.lower().startswith(("gpt-5", "o1", "o3", "o4")) else "openai_chat"
    alternate: ProviderRoute = "openai_chat" if primary == "openai_responses" else "openai_responses"
    return [primary, alternate]


def _has_explicit_route(base_url: str) -> bool:
    value = base_url.rstrip("/").lower()
    return value.endswith(("/messages", "/responses", "/chat", "/chat/completions", "/api/generate", "/api/chat")) or ":generatecontent" in value


def _endpoint_for(base_url: str, route: ProviderRoute) -> str:
    value = base_url.rstrip("/")
    if route in {"anthropic_messages", "gemini", "ollama_generate", "ollama_chat"}:
        return value
    if route == "openai_responses":
        return value if value.endswith("/responses") else (f"{value}/responses" if value.endswith("/v1") else f"{value}/v1/responses")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/chat"):
        return f"{value}/completions"
    return f"{value}/chat/completions" if value.endswith("/v1") else f"{value}/v1/chat/completions"


def _headers_for(route: ProviderRoute, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if not api_key:
        return headers
    if route == "anthropic_messages":
        return {**headers, "x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if route == "gemini":
        return {**headers, "x-goog-api-key": api_key}
    return {**headers, "Authorization": f"Bearer {api_key}"}


def _payload_for(route: ProviderRoute, model_name: str, system: str, user: str, image_data: str | None, mime_type: str | None) -> dict[str, Any]:
    if route == "openai_responses":
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user}]
        if image_data:
            content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{image_data}"})
        return {"model": model_name, "input": [{"role": "system", "content": [{"type": "input_text", "text": system}]}, {"role": "user", "content": content}]}
    if route == "openai_chat":
        user_content: str | list[dict[str, Any]] = user
        if image_data:
            user_content = [{"type": "text", "text": user}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}]
        # Optional temperature/response_format parameters are rejected by many compatible gateways.
        return {"model": model_name, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}]}
    if route == "anthropic_messages":
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        if image_data:
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime_type or "image/png", "data": image_data}})
        return {"model": model_name, "max_tokens": 2048, "system": system, "messages": [{"role": "user", "content": content}]}
    if route == "gemini":
        parts: list[dict[str, Any]] = [{"text": f"{system}\n\n{user}"}]
        if image_data:
            parts.append({"inline_data": {"mime_type": mime_type or "image/png", "data": image_data}})
        return {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}
    if route == "ollama_generate":
        payload: dict[str, Any] = {"model": model_name, "prompt": f"{system}\n\n{user}", "stream": False, "format": "json"}
        if image_data:
            payload["images"] = [image_data]
        return payload
    message: dict[str, Any] = {"role": "user", "content": user}
    if image_data:
        message["images"] = [image_data]
    return {"model": model_name, "messages": [{"role": "system", "content": system}, message], "stream": False, "format": "json"}


def _response_text(response: dict[str, Any], route: ProviderRoute) -> str:
    if route == "openai_chat":
        choices = response.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
    elif route == "openai_responses":
        content = response.get("output_text")
        if not isinstance(content, str):
            output = response.get("output")
            content = "".join(str(part.get("text") or "") for item in output if isinstance(item, dict) for part in item.get("content", []) if isinstance(part, dict) and part.get("type") == "output_text") if isinstance(output, list) else ""
    elif route == "anthropic_messages":
        blocks = response.get("content")
        content = "".join(str(block.get("text") or "") for block in blocks if isinstance(block, dict) and block.get("type") == "text") if isinstance(blocks, list) else ""
    elif route == "gemini":
        candidates = response.get("candidates")
        candidate = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
        parts = candidate.get("content", {}).get("parts") if isinstance(candidate.get("content"), dict) else None
        content = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)) if isinstance(parts, list) else ""
    elif route == "ollama_generate":
        content = response.get("response")
    else:
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Provider completion did not contain JSON content")
    return content


def _json_object(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as error:
        raise RuntimeError("Provider response was not a JSON object") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("Provider response must be a JSON object")
    return parsed


def _safe_error(error: Exception | None) -> str:
    return str(error)[:500] if error else "Unknown provider error"
