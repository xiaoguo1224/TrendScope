from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model_gateway import ModelGateway
from app.models.configuration import PromptTemplate
from app.models.research_task import ResearchTask
from app.providers.llm import LLMProvider, MockLLMProvider

EXPANSION_CATEGORIES = (
    "core_keywords", "long_tail_keywords", "trend_keywords", "audience_keywords", "scenario_keywords", "style_keywords",
)
logger = logging.getLogger(__name__)
DEFAULT_QUERY_EXPANSION_PROMPT = (
    "Expand a public-content research query without changing or removing user keywords. "
    "Return only the configured keyword categories. Topic: {topic}; platform: {platform}; goals: {research_goals}."
)


class QueryExpansionResponse(BaseModel):
    core_keywords: list[str] = Field(default_factory=list)
    long_tail_keywords: list[str] = Field(default_factory=list)
    trend_keywords: list[str] = Field(default_factory=list)
    audience_keywords: list[str] = Field(default_factory=list)
    scenario_keywords: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)


class QueryExpansionService:
    def __init__(self, database: Session, provider: LLMProvider | None = None, max_per_category: int = 5) -> None:
        self.database = database
        gateway = ModelGateway(database)
        self.provider = provider or (_QueryExpansionGatewayProvider(gateway) if gateway.has_candidate(purpose="llm") else MockLLMProvider())
        self.max_per_category = max_per_category

    async def expand(self, task: ResearchTask) -> dict[str, list[str]]:
        template = self.database.scalar(
            select(PromptTemplate).where(PromptTemplate.purpose == "query_expansion", PromptTemplate.enabled.is_(True))
        )
        template_text = template.template if template else DEFAULT_QUERY_EXPANSION_PROMPT
        prompt = self._render_prompt(template_text, task)
        context = {"platform": task.platform, "topic": task.topic, "keywords": task.keywords,
                   "time_range": task.time_range, "research_goals": task.research_goals or ""}
        contract = (
            " Return exactly one JSON object with six array fields: core_keywords, long_tail_keywords, "
            "trend_keywords, audience_keywords, scenario_keywords, style_keywords. Preserve every input keyword "
            "in core_keywords and add at least two distinct, search-ready supplementary keywords when evidence permits. "
            "Every array item must be a plain string; do not return prose or nested objects."
        )
        response = await self.provider.generate_structured(
            prompt=prompt + contract,
            context=context,
        )
        try:
            parsed = QueryExpansionResponse.model_validate(response)
            result = self._validate(parsed.model_dump(), task.keywords)
        except ValidationError as error:
            result = await self._repair(response, prompt, contract, context, task, str(error))
        if not self._has_supplement(result, task.keywords):
            result = await self._repair(
                response, prompt, contract, context, task,
                "The JSON preserved only the user input. Add distinct supplementary search keywords now.",
            )
        if self._has_supplement(result, task.keywords):
            return result
        return self._fallback(task)

    async def _repair(
        self, response: object, prompt: str, contract: str, context: dict[str, object], task: ResearchTask, reason: str,
    ) -> dict[str, list[str]]:
        try:
            repaired = await self.provider.generate_structured(
                prompt=f"Repair the previous query-expansion result. {reason}\n{prompt}{contract}",
                context={**context, "previous_json": response},
            )
            return self._validate(QueryExpansionResponse.model_validate(repaired).model_dump(), task.keywords)
        except (ValidationError, RuntimeError, ValueError, TypeError) as error:
            logger.warning("query_expansion_repair_failed task_id=%s error=%s", task.id, error)
            return {category: [] for category in EXPANSION_CATEGORIES}

    @staticmethod
    def _has_supplement(result: dict[str, list[str]], original_keywords: list[str]) -> bool:
        originals = {value.strip().casefold() for value in original_keywords if value.strip()}
        return any(value.casefold() not in originals for values in result.values() for value in values)

    def _fallback(self, task: ResearchTask) -> dict[str, list[str]]:
        """Keep collection usable when a provider cannot return the required JSON."""
        result = self._validate({}, task.keywords)
        topic = task.topic.strip()
        if not topic:
            return result
        chinese = bool(re.search(r"[\u3400-\u9fff]", topic))
        candidates = ([f"{topic} 热门", f"{topic} 趋势", f"{topic} 灵感"] if chinese else [f"{topic} trends", f"{topic} ideas", f"best {topic}"])
        for value in candidates:
            if value.casefold() not in {existing.casefold() for values in result.values() for existing in values}:
                result["long_tail_keywords"].append(value)
        logger.warning("query_expansion_fallback_used task_id=%s", task.id)
        return result

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


class _QueryExpansionGatewayProvider:
    """Routes query expansion through the same gateway as analysis."""

    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return await self.gateway.generate_structured(purpose="llm", prompt=prompt, context=context)
