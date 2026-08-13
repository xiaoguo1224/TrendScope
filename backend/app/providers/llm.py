from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, list[str]]: ...


class MockLLMProvider:
    """Deterministic provider used when no configured external provider is available."""

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, list[str]]:
        topic = str(context.get("topic", "")).strip()
        keywords = [str(value).strip() for value in context.get("keywords", []) if str(value).strip()]
        primary = keywords[0] if keywords else topic
        return {
            "core_keywords": [topic] if topic else [],
            "long_tail_keywords": [f"{primary} guide"] if primary else [],
            "trend_keywords": [f"{primary} trends"] if primary else [],
            "audience_keywords": [],
            "scenario_keywords": [],
            "style_keywords": [],
        }
