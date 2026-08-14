from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]: ...


class MockLLMProvider:
    """Deterministic provider used when no configured external provider is available."""

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        analysis_type = str(context.get("analysis_type", ""))
        if analysis_type == "tool_plan":
            return {"calls": [{"name": "get_ranked_contents", "arguments": {"board": "Hot", "limit": 8}}]}
        if analysis_type == "task_summary":
            observations = context.get("tool_observations", [])
            item_count = sum(
                len(item.get("result", {}).get("items", []))
                for item in observations if isinstance(item, dict) and isinstance(item.get("result"), dict)
            )
            topic = str(context.get("task", {}).get("topic", "this topic")) if isinstance(context.get("task"), dict) else "this topic"
            return {
                "copywriting_summary": f"The representative {topic} content uses concise, topic-led framing.",
                "visual_summary": "No representative local image was available for visual synthesis.",
                "audience_summary": "Audience evidence is limited to the collected public content.",
                "popularity_summary": f"The conclusion is based on {item_count} ranked representative items and their observed public metrics.",
                "reusable_patterns": ["Use a clear topic-led opening"], "trend_tags": [topic],
                "evidence": [f"Read {item_count} ranked representative items through task-scoped tools."],
                "limitations": ["Offline mock analysis does not infer visual details beyond available evidence."],
                "hot_topics": [topic], "rising_topics": [], "visual_patterns": [],
                "copywriting_patterns": ["Use a clear topic-led opening"], "audience_patterns": [],
                "scenario_patterns": [], "style_patterns": [], "domain_patterns": [],
            }
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
