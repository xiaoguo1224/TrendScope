from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

from app.models.configuration import AIProviderConfig
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.configuration import AIProviderConfigTestRead

logger = logging.getLogger(__name__)

# A synthetic transparent 1×1 PNG. It never contains user or platform data.
_TEST_IMAGE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL6yAAAAABJRU5ErkJggg==")


class ProviderConfigurationTestService:
    """Verifies one saved provider configuration without persisting an analysis result."""

    def __init__(self, *, provider_factory: Callable[[AIProviderConfig], OpenAICompatibleProvider] = OpenAICompatibleProvider) -> None:
        self.provider_factory = provider_factory

    async def run(self, config: AIProviderConfig) -> AIProviderConfigTestRead:
        try:
            provider = self.provider_factory(config)
            if config.provider_type == "vision":
                response = await provider.analyze_image_bytes(
                    image_bytes=_TEST_IMAGE,
                    mime_type="image/png",
                    prompt="Return exactly this JSON object: {\"ok\": true, \"test\": \"vision\"}.",
                    context={"analysis_type": "provider_connection_test"},
                )
            else:
                response = await provider.generate_structured(
                    prompt="Return exactly this JSON object: {\"ok\": true, \"test\": \"llm\"}.",
                    context={"analysis_type": "provider_connection_test"},
                )
            return AIProviderConfigTestRead(
                success=True,
                endpoint=getattr(provider, "last_endpoint", config.base_url),
                response_preview=json.dumps(response, ensure_ascii=False)[:500],
                message="Model configuration test succeeded.",
            )
        except Exception as error:
            logger.warning("ai_provider_configuration_test_failed type=%s name=%s", config.provider_type, config.name, exc_info=True)
            detail = str(error).strip() or error.__class__.__name__
            return AIProviderConfigTestRead(success=False, endpoint=config.base_url or "", message=f"Model configuration test failed: {detail[:500]}")
