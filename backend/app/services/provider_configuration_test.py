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
# A regular 32×32 PNG generated and locally decoded during development. Some
# provider gateways reject transparent 1×1 PNGs even though they are technically valid.
_TEST_IMAGE = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAACXBIWXMAAAABAAAAAQBPJcTWAAAAOElEQVR4nO3RwQ0AMAjDwFRi/5XTEcyHn2+AIJnXNpfmdD0eWPAHyETIRMhEyETIRMhEyETIRCEfP+8Dewk/pooAAAAASUVORK5CYII=")


class ProviderConfigurationTestService:
    """Verifies one saved provider configuration without persisting an analysis result."""

    def __init__(self, *, provider_factory: Callable[[AIProviderConfig], OpenAICompatibleProvider] = OpenAICompatibleProvider) -> None:
        self.provider_factory = provider_factory

    async def run(self, config: AIProviderConfig) -> AIProviderConfigTestRead:
        provider: OpenAICompatibleProvider | None = None
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
                request_preview=getattr(provider, "last_request_preview", None),
                response_preview=json.dumps(response, ensure_ascii=False)[:500],
                message="Model configuration test succeeded.",
            )
        except Exception as error:
            logger.warning("ai_provider_configuration_test_failed type=%s name=%s", config.provider_type, config.name, exc_info=True)
            detail = str(error).strip() or error.__class__.__name__
            return AIProviderConfigTestRead(
                success=False,
                endpoint=getattr(provider, "last_endpoint", config.base_url or ""),
                request_preview=getattr(provider, "last_request_preview", None),
                message=f"Model configuration test failed: {detail[:500]}",
            )
