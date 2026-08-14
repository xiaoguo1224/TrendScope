from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.models.configuration import AIProviderConfig
from app.media import detect_image_mime


ProviderRoute = Literal["openai_responses", "openai_chat", "anthropic_messages", "gemini", "ollama_generate", "ollama_chat"]


class OpenAICompatibleProvider:
    """Protocol adapter used by :class:`app.model_gateway.ModelGateway`.

    The gateway selects this adapter from the saved protocol configuration.  Its
    URL helpers only construct an endpoint inside the chosen protocol; business
    services never inspect either the URL or a vendor response envelope.
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
        self.protocol: ProviderRoute | Literal["auto"] = getattr(config, "protocol", "auto") or "auto"
        if self.protocol not in {"auto", "openai_responses", "openai_chat", "anthropic_messages", "gemini", "ollama_generate", "ollama_chat"}:
            raise ValueError(f"Unsupported AI provider protocol '{self.protocol}'")
        self.last_endpoint = config.base_url
        self.last_request_preview: str | None = None

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = "Return exactly one JSON object. Do not use Markdown fences or add commentary."
        user = f"{prompt}\n\nContext JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        return _json_object(await self._request(system=system, user=user))

    async def analyze_image(self, *, image_path: Path, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        image_bytes = image_path.read_bytes()
        mime_type = detect_image_mime(image_bytes, image_path.name)
        if mime_type is None:
            raise ValueError(
                f"Local media '{image_path.name}' is not a supported JPEG, PNG, GIF, or WebP image; it was not sent to the vision provider."
            )
        return await self.analyze_image_bytes(
            image_bytes=image_bytes, mime_type=mime_type, prompt=prompt, context=context,
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
        for route in _routes_to_try(self.base_url, self.model_name, self.protocol):
            endpoint = _endpoint_for(self.base_url, route)
            payload = _payload_for(route, self.model_name, system, user, image_data, mime_type)
            headers = _headers_for(route, self.api_key)
            self.last_request_preview = _request_preview(route, payload)
            for attempt in range(self.max_retries + 1):
                try:
                    response = await asyncio.to_thread(self._post, endpoint, payload, headers)
                    self.last_endpoint = endpoint
                    return _response_text(response, route)
                except Exception as error:
                    last_error = error
                    # Retrying an already-completed empty response or a declared
                    # protocol mismatch is wasteful; move to the next adapter.
                    if _can_try_next_route(error):
                        break
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
            # An explicit endpoint must never be silently redirected to another API.
            # For a plain base URL, compatible gateways may expose only one of
            # Responses, Chat Completions, or Anthropic Messages.
            if _has_explicit_route(self.base_url) or not _can_try_next_route(last_error):
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
        if raw.lstrip().startswith("event:"):
            return _sse_response(raw)
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


def _routes_to_try(base_url: str, model_name: str, protocol: ProviderRoute | Literal["auto"] = "auto") -> list[ProviderRoute]:
    if protocol != "auto":
        return [protocol]
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
    # Claude Code-compatible gateways (including router applications) commonly
    # expose /v1/messages even when their routed model is named like a GPT model.
    return [primary, alternate, "anthropic_messages"]


def _has_explicit_route(base_url: str) -> bool:
    value = base_url.rstrip("/").lower()
    return value.endswith(("/messages", "/responses", "/chat", "/chat/completions", "/api/generate", "/api/chat")) or ":generatecontent" in value


def _endpoint_for(base_url: str, route: ProviderRoute) -> str:
    value = base_url.rstrip("/")
    if route == "anthropic_messages":
        return value if value.endswith("/messages") else (f"{value}/messages" if value.endswith("/v1") else f"{value}/v1/messages")
    if route in {"gemini", "ollama_generate", "ollama_chat"}:
        return value
    if route == "openai_responses":
        return value if value.endswith("/responses") else (f"{value}/responses" if value.endswith("/v1") else f"{value}/v1/responses")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/chat"):
        return f"{value}/completions"
    return f"{value}/chat/completions" if value.endswith("/v1") else f"{value}/v1/chat/completions"


def _can_try_next_route(error: Exception | None) -> bool:
    detail = str(error).lower() if error else ""
    return "protocol_not_supported" in detail or "completed but returned an empty output" in detail


def _headers_for(route: ProviderRoute, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if not api_key:
        return headers
    if route == "anthropic_messages":
        return {**headers, "x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if route == "gemini":
        return {**headers, "x-goog-api-key": api_key}
    if route == "openai_responses":
        return {**headers, "Authorization": f"Bearer {api_key}", "Accept": "text/event-stream"}
    return {**headers, "Authorization": f"Bearer {api_key}"}


def _payload_for(route: ProviderRoute, model_name: str, system: str, user: str, image_data: str | None, mime_type: str | None) -> dict[str, Any]:
    if route == "openai_responses":
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user}]
        if image_data:
            # Some Responses-compatible gateways accept text with system/user
            # input entries but only process images when instructions are top-level
            # and the image specifies an explicit detail mode.
            content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{image_data}", "detail": "auto"})
            return {
                "model": model_name,
                "instructions": system,
                "input": [{"role": "user", "content": content}],
                "max_output_tokens": 2048,
                "stream": True,
            }
        return {
            "model": model_name,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": content},
            ],
            # A bounded output budget prevents compatible Responses gateways
            # from returning an incomplete response with no output payload.
            "max_output_tokens": 2048,
            "stream": True,
        }
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
    failure = _provider_failure_detail(response)
    if failure:
        raise RuntimeError(f"Provider response failed: {failure}")
    extractors = {
        "openai_chat": (_openai_chat_text, _openai_responses_text),
        "openai_responses": (_openai_responses_text, _openai_chat_text),
        "anthropic_messages": (_anthropic_text, _openai_chat_text, _openai_responses_text),
        "gemini": (_gemini_text, _openai_chat_text, _openai_responses_text),
        "ollama_generate": (_ollama_generate_text, _ollama_chat_text),
        "ollama_chat": (_ollama_chat_text, _ollama_generate_text),
    }
    # Several gateways accept one wire format but return another vendor's
    # completion envelope. Parse known envelopes before declaring the request bad.
    for extract in extractors[route]:
        content = extract(response)
        if content:
            return content
    if response.get("status") == "completed" and response.get("output") == []:
        raise RuntimeError(
            "Provider marked the request completed but returned an empty output. "
            "The configured API route did not produce a completion."
        )
    response_keys = ", ".join(sorted(str(key) for key in response.keys())[:12])
    raise RuntimeError(f"Provider completion did not contain JSON content (response keys: {response_keys or 'none'})")


def _provider_failure_detail(response: dict[str, Any]) -> str | None:
    error = response.get("error")
    if error:
        return _safe_response_detail(error)
    status = response.get("status")
    if isinstance(status, str) and status.lower() not in {"completed", "succeeded"}:
        incomplete = response.get("incomplete_details")
        detail = _safe_response_detail(incomplete) if incomplete else None
        return f"status={status}" + (f"; {detail}" if detail else "")
    return None


def _safe_response_detail(value: object) -> str:
    if isinstance(value, dict):
        message = value.get("message") or value.get("reason") or value.get("code")
        if message:
            return str(message)[:400]
        return ", ".join(f"{key}={str(item)[:120]}" for key, item in value.items())[:400] or "unknown provider error"
    return str(value)[:400]


def _sse_response(raw: str) -> dict[str, Any]:
    """Convert a Responses SSE stream into the minimal completion envelope we consume.

    Some OpenAI-compatible gateways emit text only as ``response.output_text.delta``
    events and leave the terminal JSON object's ``output`` array empty.
    """
    deltas: list[str] = []
    error: object | None = None
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str):
            deltas.append(event["delta"])
        elif event.get("type") in {"error", "response.failed"}:
            error = event.get("error") or event.get("response")
    if deltas:
        return {"output_text": "".join(deltas)}
    if error:
        raise RuntimeError(f"Provider streaming response failed: {_safe_response_detail(error)}")
    raise RuntimeError("Provider streaming response did not contain output text")


def _request_preview(route: ProviderRoute, payload: dict[str, Any]) -> str:
    """Provide a UI-safe trace of the synthetic test request without credentials or image bytes."""
    safe = _redact_test_media(json.loads(json.dumps(payload)))
    return json.dumps({"route": route, "payload": safe}, ensure_ascii=False)[:2000]


def _redact_test_media(value: object) -> object:
    if isinstance(value, list):
        return [_redact_test_media(item) for item in value]
    if not isinstance(value, dict):
        return value
    safe: dict[str, object] = {}
    for key, item in value.items():
        if key in {"data", "images"} or (key == "image_url" and isinstance(item, str) and item.startswith("data:")):
            safe[key] = "<built-in test image omitted>"
        else:
            safe[key] = _redact_test_media(item)
    return safe


def _openai_chat_text(response: dict[str, Any]) -> str | None:
    choices = response.get("choices")
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    return _content_to_text(message.get("content") if isinstance(message, dict) else None)


def _openai_responses_text(response: dict[str, Any]) -> str | None:
    direct = _content_to_text(response.get("output_text"))
    if direct:
        return direct
    output = response.get("output")
    if not isinstance(output, list):
        return None
    parts = [
        part for item in output if isinstance(item, dict)
        for part in item.get("content", []) if isinstance(part, dict) and part.get("type") in {"output_text", "text"}
    ]
    return _content_to_text(parts)


def _anthropic_text(response: dict[str, Any]) -> str | None:
    blocks = response.get("content")
    return _content_to_text([block for block in blocks if isinstance(block, dict) and block.get("type") == "text"]) if isinstance(blocks, list) else None


def _gemini_text(response: dict[str, Any]) -> str | None:
    candidates = response.get("candidates")
    candidate = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
    content = candidate.get("content") if isinstance(candidate.get("content"), dict) else {}
    return _content_to_text(content.get("parts"))


def _ollama_generate_text(response: dict[str, Any]) -> str | None:
    return _content_to_text(response.get("response"))


def _ollama_chat_text(response: dict[str, Any]) -> str | None:
    message = response.get("message")
    return _content_to_text(message.get("content") if isinstance(message, dict) else None)


def _content_to_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, list):
        text = "".join(str(item.get("text") or "") for item in value if isinstance(item, dict))
        return text if text.strip() else None
    return None


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
