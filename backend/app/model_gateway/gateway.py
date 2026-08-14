from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model_gateway.capabilities import ModelCapabilities
from app.model_gateway.schemas import ModelRequest, ModelResponse
from app.models.configuration import AIProviderConfig
from app.providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class NoEligibleModel(RuntimeError):
    """There is no enabled, complete model configuration for a requested role."""


class UnsupportedCapability(RuntimeError):
    """Configured models exist but none supports the required input capability."""


ProviderFactory = Callable[[AIProviderConfig], OpenAICompatibleProvider]


class ModelGateway:
    """Routes business requests to configured protocol adapters.

    Services identify a purpose (``llm`` or ``vision``) and required capability;
    they never select a URL, vendor SDK, protocol path, or concrete model name.
    """

    def __init__(
        self,
        database: Session | None = None,
        *,
        configurations: Iterable[AIProviderConfig] | None = None,
        provider_factory: ProviderFactory = OpenAICompatibleProvider,
    ) -> None:
        self.database = database
        self._configurations = list(configurations) if configurations is not None else None
        self.provider_factory = provider_factory
        self.last_endpoint = ""
        self.last_request_preview: str | None = None

    def has_candidate(self, *, purpose: str) -> bool:
        return any(self._is_complete(config) for config in self._candidates(purpose))

    async def generate_structured(
        self, *, purpose: str, prompt: str, context: dict[str, Any], image_path: Path | None = None,
    ) -> dict[str, Any]:
        response = await self.generate(ModelRequest(
            purpose=purpose, prompt=prompt, context=context, image_path=image_path,
        ))
        return response.data

    async def generate(self, request: ModelRequest) -> ModelResponse:
        required = ["vision" if request.image_path is not None else "text"]
        if request.require_structured_output:
            required.append("structured_output")
        candidates = self._candidates(request.purpose)
        if not candidates:
            raise NoEligibleModel(f"No enabled model is configured for purpose '{request.purpose}'.")
        capable = [
            config for config in candidates
            if all(ModelCapabilities.from_config(config.capabilities, provider_type=config.provider_type).supports(capability) for capability in required)
        ]
        if not capable:
            raise UnsupportedCapability(
                f"No enabled '{request.purpose}' model supports required capabilities: {', '.join(required)}."
            )

        last_error: Exception | None = None
        for index, config in enumerate(capable):
            provider: OpenAICompatibleProvider | None = None
            try:
                provider = self.provider_factory(config)
                if request.image_path is None:
                    result = await provider.generate_structured(prompt=request.prompt, context=request.context)
                else:
                    result = await provider.analyze_image(image_path=request.image_path, prompt=request.prompt, context=request.context)
                self.last_endpoint = provider.last_endpoint
                self.last_request_preview = provider.last_request_preview
                return ModelResponse(
                    data=result, provider_name=config.name, model_name=config.model_name or "", endpoint=provider.last_endpoint,
                )
            except Exception as error:
                last_error = error
                self.last_endpoint = provider.last_endpoint if provider is not None else config.base_url or ""
                self.last_request_preview = provider.last_request_preview if provider is not None else None
                if index == len(capable) - 1 or not _is_retryable_provider_error(error):
                    break
                logger.warning(
                    "model_gateway_fallback purpose=%s failed_provider=%s next_provider=%s error=%s",
                    request.purpose, config.name, capable[index + 1].name, _safe_error(error),
                )
        raise RuntimeError(f"Model request for '{request.purpose}' failed: {_safe_error(last_error)}") from last_error

    def _candidates(self, purpose: str) -> list[AIProviderConfig]:
        if self._configurations is None:
            if self.database is None:
                return []
            configurations = list(self.database.scalars(
                select(AIProviderConfig).where(
                    AIProviderConfig.provider_type == purpose,
                    AIProviderConfig.enabled.is_(True),
                ).order_by(AIProviderConfig.priority, AIProviderConfig.id)
            ))
        else:
            configurations = self._configurations
        return [config for config in configurations if config.provider_type == purpose and config.enabled and self._is_complete(config)]

    @staticmethod
    def _is_complete(config: AIProviderConfig) -> bool:
        return bool(config.base_url and config.model_name)


def _is_retryable_provider_error(error: Exception) -> bool:
    detail = str(error).lower()
    if any(marker in detail for marker in ("timeout", "timed out", "network error", "connection reset", "connection refused", "temporarily unavailable", "provider unavailable")):
        return True
    return any(f"http {status}" in detail for status in (429, 500, 501, 502, 503, 504))


def _safe_error(error: Exception | None) -> str:
    return str(error)[:500] if error else "Unknown provider error"
