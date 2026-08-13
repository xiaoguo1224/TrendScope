from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]: ...


class MockLLMProvider:
    """Deterministic provider used when no configured external provider is available."""

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        analysis_type = str(context.get("analysis_type", ""))
        if analysis_type == "text":
            title = str(context.get("title") or "").strip()
            text = str(context.get("text") or "").strip()
            topic = str(context.get("topic") or "").strip()
            first_line = text.splitlines()[0].strip() if text else title
            return {
                "hook_type": "informational" if title or text else "unknown",
                "title_structure": "descriptive" if title else "not_available",
                "opening_hook": first_line[:240],
                "writing_style": "concise" if len(text) < 500 else "detailed",
                "emotion": "neutral",
                "pain_points": [], "benefits": [], "target_audience": [], "scenario": [], "cta": None,
                "hashtags": [], "topic_tags": [topic] if topic else [],
                "reusable_patterns": ["Use a clear topic-led opening"] if first_line else [],
            }
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
