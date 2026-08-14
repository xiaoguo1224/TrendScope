from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.configuration import ensure_analysis_defaults
from app.models.analysis import ContentAnalysisRecord, TrendAnalysisRecord
from app.models.configuration import AIProviderConfig, PromptTemplate
from app.models.content import ContentItem
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.providers.llm import LLMProvider, MockLLMProvider
from app.providers.vision import MockVisionProvider, VisionProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.analysis import (
    AnalysisItemRead, ContentAnalysis, RankedContentItem, TextAnalysis, TrendAnalysisRead, VisualAnalysis,
)
from app.services.ranking import RankingService

logger = logging.getLogger(__name__)


class AnalysisService:
    """Runs schema-validated analysis while containing failures to one content item."""

    def __init__(
        self, database: Session, *, llm_provider: LLMProvider | None = None, vision_provider: VisionProvider | None = None,
    ) -> None:
        self.database = database
        # An enabled, complete provider configuration takes precedence; mock providers keep offline use possible.
        self.llm_provider = llm_provider or self._llm_provider()
        self.vision_provider = vision_provider or self._vision_provider()

    async def analyze_task(self, task: ResearchTask) -> list[AnalysisItemRead]:
        ensure_analysis_defaults(self.database)
        rankings = RankingService(self.database).rank_task(task.id)
        ranked = {item.content_item_id: item for board in rankings.boards if board.name == "Hot" for item in board.items}
        contents = list(self.database.scalars(select(ContentItem).where(ContentItem.research_task_id == task.id)))
        results: list[AnalysisItemRead] = []
        failures = False
        for content in contents:
            record = self.database.scalar(select(ContentAnalysisRecord).where(ContentAnalysisRecord.content_item_id == content.id))
            if record is None:
                record = ContentAnalysisRecord(content_item_id=content.id, visual_analyses=[])
                self.database.add(record)
            score = ranked.get(content.id)
            try:
                text_analysis = await self._analyze_text(task, content)
                visual_analyses = await self._analyze_images(task, content)
                content_analysis = self._build_content_analysis(content, score, text_analysis, visual_analyses)
                record.text_analysis = text_analysis.model_dump(mode="json")
                record.visual_analyses = [item.model_dump(mode="json") for item in visual_analyses]
                record.content_analysis = content_analysis.model_dump(mode="json")
                record.analysis_error = None
                self.database.commit()
                self.database.refresh(record)
            except Exception as error:
                self.database.rollback()
                failures = True
                record = self.database.scalar(select(ContentAnalysisRecord).where(ContentAnalysisRecord.content_item_id == content.id))
                if record is None:
                    record = ContentAnalysisRecord(content_item_id=content.id, visual_analyses=[])
                    self.database.add(record)
                record.text_analysis = None
                record.visual_analyses = []
                record.content_analysis = None
                record.analysis_error = self._safe_error(error)
                self.database.commit()
                self.database.refresh(record)
                logger.warning("content_analysis_failed task_id=%s content_id=%s", task.id, content.id, exc_info=True)
            results.append(self._response(content, record, score))
        if contents:
            task.status = ResearchTaskStatus.PARTIAL if failures else ResearchTaskStatus.COMPLETED
            task.error_message = "One or more content analyses failed" if failures else None
            self.database.commit()
        return results

    async def trends_for_task(self, task: ResearchTask) -> TrendAnalysisRead:
        await self.analyze_task(task)
        records = list(self.database.scalars(
            select(ContentAnalysisRecord).join(ContentItem).where(
                ContentItem.research_task_id == task.id, ContentAnalysisRecord.analysis_error.is_(None),
            )
        ))
        result = self._aggregate(task.id, records)
        persisted = self.database.scalar(select(TrendAnalysisRecord).where(TrendAnalysisRecord.research_task_id == task.id))
        if persisted is None:
            persisted = TrendAnalysisRecord(research_task_id=task.id, result=result.model_dump(mode="json"))
            self.database.add(persisted)
        else:
            persisted.result = result.model_dump(mode="json")
        self.database.commit()
        return result

    async def _analyze_text(self, task: ResearchTask, content: ContentItem) -> TextAnalysis:
        response = await self.llm_provider.generate_structured(
            prompt=self._prompt("text_analysis", task),
            context={"analysis_type": "text", "topic": task.topic, "platform": task.platform, "title": content.title or "", "text": content.text or ""},
        )
        return TextAnalysis.model_validate(response)

    async def _analyze_images(self, task: ResearchTask, content: ContentItem) -> list[VisualAnalysis]:
        analyses: list[VisualAnalysis] = []
        for local_path in content.local_image_paths or []:
            image_path = Path(local_path)
            if not image_path.is_file():
                logger.warning("local_analysis_image_missing content_id=%s", content.id)
                continue
            response = await self.vision_provider.analyze_image(
                image_path=image_path, prompt=self._prompt("visual_analysis", task),
                context={"topic": task.topic, "platform": task.platform, "title": content.title or "", "content_id": content.id},
            )
            analyses.append(VisualAnalysis.model_validate(response))
        return analyses

    def _prompt(self, purpose: str, task: ResearchTask) -> str:
        template = self.database.scalar(select(PromptTemplate).where(PromptTemplate.purpose == purpose, PromptTemplate.enabled.is_(True)))
        value = template.template if template else ""
        return value.replace("{topic}", task.topic).replace("{platform}", task.platform).replace("{research_goals}", task.research_goals or "")

    def _llm_provider(self) -> LLMProvider:
        configured = self._configured_provider("llm")
        return self._configured_or_mock(configured, MockLLMProvider())

    def _vision_provider(self) -> VisionProvider:
        configured = self._configured_provider("vision")
        return self._configured_or_mock(configured, MockVisionProvider())

    @staticmethod
    def _configured_or_mock(configured: AIProviderConfig | None, fallback: LLMProvider | VisionProvider) -> LLMProvider | VisionProvider:
        if configured is None:
            return fallback
        try:
            return OpenAICompatibleProvider(configured)
        except ValueError as error:
            logger.warning("analysis_provider_configuration_incomplete type=%s name=%s detail=%s", configured.provider_type, configured.name, error)
            return fallback

    def _configured_provider(self, provider_type: str) -> AIProviderConfig | None:
        # Deliberately never log api_key or return it to callers.
        configured = self.database.scalar(
            select(AIProviderConfig).where(
                AIProviderConfig.provider_type == provider_type, AIProviderConfig.enabled.is_(True),
            ).order_by(AIProviderConfig.id)
        )
        if configured is not None:
            logger.info("analysis_provider_selected type=%s name=%s model=%s", provider_type, configured.name, configured.model_name)
        return configured

    @staticmethod
    def _build_content_analysis(
        content: ContentItem, score: RankedContentItem | None, text: TextAnalysis, visual: list[VisualAnalysis],
    ) -> ContentAnalysis:
        metrics = _metrics(content)
        evidence = [f"Observed {name}={value}" for name, value in metrics.items()]
        if score is not None:
            evidence.extend([f"Computed engagement_score={score.engagement_score}", f"Computed freshness_score={score.freshness_score}"])
            if score.growth_score is not None:
                evidence.append(f"Computed growth_score={score.growth_score}")
        limitations = []
        if score is None or score.growth_score is None:
            limitations.append("Growth inference is unavailable without at least two metric snapshots.")
        if not visual:
            limitations.append("No available local image was analyzed.")
        return ContentAnalysis(
            why_it_may_be_popular="The explanation is an AI inference informed by the separate objective evidence.",
            core_content_elements=[text.hook_type, text.title_structure, *text.reusable_patterns],
            core_visual_elements=[item.style for item in visual if item.style != "not_classified"],
            target_audience=text.target_audience or [audience for item in visual for audience in item.target_audience],
            emotional_value=text.emotion, reusable_patterns=list(dict.fromkeys([*text.reusable_patterns, *[pattern for item in visual for pattern in item.reusable_visual_patterns]])),
            trend_tags=text.topic_tags, evidence=evidence, limitations=limitations,
        )

    @staticmethod
    def _response(content: ContentItem, record: ContentAnalysisRecord, score: RankedContentItem | None) -> AnalysisItemRead:
        objective_facts: dict[str, Any] = {"metrics": _metrics(content), "published_at": content.published_at, "collected_at": content.collected_at}
        if score is not None:
            objective_facts["ranking"] = score.model_dump(mode="json")
        return AnalysisItemRead(
            content_item_id=content.id, title=content.title, url=content.url, local_image_paths=content.local_image_paths or [],
            objective_facts=objective_facts, text_analysis=TextAnalysis.model_validate(record.text_analysis) if record.text_analysis else None,
            visual_analyses=[VisualAnalysis.model_validate(item) for item in record.visual_analyses or []],
            content_analysis=ContentAnalysis.model_validate(record.content_analysis) if record.content_analysis else None,
            analysis_error=record.analysis_error, analyzed_at=record.analyzed_at,
        )

    @staticmethod
    def _aggregate(task_id: int, records: Iterable[ContentAnalysisRecord]) -> TrendAnalysisRead:
        usable = list(records)
        if len(usable) < 2:
            return TrendAnalysisRead(task_id=task_id, insufficient_data=True, limitation="At least two successfully analyzed content items are required for cross-content trend aggregation.", analyzed_content_count=len(usable))
        texts = [TextAnalysis.model_validate(record.text_analysis) for record in usable if record.text_analysis]
        visuals = [VisualAnalysis.model_validate(item) for record in usable for item in record.visual_analyses or []]
        contents = [ContentAnalysis.model_validate(record.content_analysis) for record in usable if record.content_analysis]
        return TrendAnalysisRead(
            task_id=task_id, insufficient_data=False, analyzed_content_count=len(usable),
            hot_topics=_top(tag for item in texts for tag in item.topic_tags),
            rising_topics=_top(tag for item in contents for tag in item.trend_tags),
            visual_patterns=_top(pattern for item in visuals for pattern in item.reusable_visual_patterns),
            copywriting_patterns=_top(pattern for item in texts for pattern in item.reusable_patterns),
            audience_patterns=_top(audience for item in texts for audience in item.target_audience),
            scenario_patterns=_top(scenario for item in texts for scenario in item.scenario),
            style_patterns=_top(item.style for item in visuals if item.style != "not_classified"),
            domain_patterns=_top(f"{key}={value}" for item in visuals for key, value in item.domain_attributes.items()),
        )

    @staticmethod
    def _safe_error(error: Exception) -> str:
        return str(error)[:500] or error.__class__.__name__


def _metrics(content: ContentItem) -> dict[str, int]:
    return {name: int(value) for name in ("like_count", "favorite_count", "comment_count", "share_count", "view_count") if (value := getattr(content, name)) is not None}


def _top(values: Iterable[str], limit: int = 10) -> list[str]:
    return [value for value, _ in Counter(value for value in values if value).most_common(limit)]
