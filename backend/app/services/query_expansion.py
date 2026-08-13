from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import PromptTemplate
from app.models.research_task import ResearchTask
from app.providers.llm import LLMProvider, MockLLMProvider

EXPANSION_CATEGORIES = (
    "core_keywords", "long_tail_keywords", "trend_keywords", "audience_keywords", "scenario_keywords", "style_keywords",
)
DEFAULT_QUERY_EXPANSION_PROMPT = (
    "Expand a public-content research query without changing or removing user keywords. "
    "Return only the configured keyword categories. Topic: {topic}; platform: {platform}; goals: {research_goals}."
)


class QueryExpansionService:
    def __init__(self, database: Session, provider: LLMProvider | None = None, max_per_category: int = 5) -> None:
        self.database = database
        self.provider = provider or MockLLMProvider()
        self.max_per_category = max_per_category

    async def expand(self, task: ResearchTask) -> dict[str, list[str]]:
        template = self.database.scalar(
            select(PromptTemplate).where(PromptTemplate.purpose == "query_expansion", PromptTemplate.enabled.is_(True))
        )
        prompt = self._render_prompt(template.template if template else DEFAULT_QUERY_EXPANSION_PROMPT, task)
        response = await self.provider.generate_structured(
            prompt=prompt,
            context={"platform": task.platform, "topic": task.topic, "keywords": task.keywords,
                     "time_range": task.time_range, "research_goals": task.research_goals or ""},
        )
        return self._validate(response, task.keywords)

    @staticmethod
    def _render_prompt(template: str, task: ResearchTask) -> str:
        # Configurable prompts are user authored; unknown braces must not break task execution.
        values = {"platform": task.platform, "topic": task.topic, "research_goals": task.research_goals or "", "keywords": ", ".join(task.keywords)}
        for name, value in values.items():
            template = template.replace("{" + name + "}", value)
        return template

    def _validate(self, response: dict[str, Any], original_keywords: list[str]) -> dict[str, list[str]]:
        result = {category: [] for category in EXPANSION_CATEGORIES}
        seen: set[str] = set()
        for keyword in original_keywords:
            normalized = keyword.strip()
            if normalized and normalized.casefold() not in seen:
                result["core_keywords"].append(normalized)
                seen.add(normalized.casefold())
        for category in EXPANSION_CATEGORIES:
            values = response.get(category, []) if isinstance(response, dict) else []
            if not isinstance(values, list):
                continue
            for value in values:
                normalized = str(value).strip()
                if not normalized or normalized.casefold() in seen or len(result[category]) >= self.max_per_category:
                    continue
                result[category].append(normalized)
                seen.add(normalized.casefold())
        return result
