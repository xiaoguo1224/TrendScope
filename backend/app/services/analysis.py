from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.configuration import ensure_analysis_defaults
from app.models.analysis import ContentAnalysisRecord, TrendAnalysisRecord
from app.models.configuration import PromptTemplate
from app.models.content import ContentItem
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.model_gateway import ModelGateway
from app.providers.llm import LLMProvider, MockLLMProvider
from app.providers.vision import MockVisionProvider, VisionProvider
from app.schemas.analysis import (
    AnalysisItemRead, ContentAnalysis, RankedContentItem, TextAnalysis, TrendAnalysisRead, VisualAnalysis,
)
from app.services.ranking import RankingService

logger = logging.getLogger(__name__)

TEXT_ANALYSIS_CONTRACT = """
Return one JSON object using exactly these fields:
hook_type, title_structure, opening_hook, writing_style, emotion, pain_points,
benefits, target_audience, scenario, cta, hashtags, topic_tags, reusable_patterns.
All fields except cta are required. Use a concise string for every scalar; use []
when an array has no supported value; cta may be null. Every array item must be a
plain string. Do not return topic, platform, explanations, nested content_structure,
or any fields outside this contract.
""".strip()

VISUAL_ANALYSIS_CONTRACT = """
Return one JSON object using exactly these fields:
subject, main_colors, secondary_colors, style, composition, camera_angle, lighting,
background, visual_focus, scene, mood, target_audience, notable_elements,
reusable_visual_patterns, domain_attributes, confidence.
All fields are required. Use strings for scalar fields, arrays of plain strings,
an object only for domain_attributes, and a confidence number from 0 to 1. Use []
or {} when evidence is unavailable. Do not return prose or extra fields.
""".strip()


class AnalysisService:
    """Runs schema-validated analysis while containing failures to one content item."""

    def __init__(
        self, database: Session, *, llm_provider: LLMProvider | None = None, vision_provider: VisionProvider | None = None,
        model_gateway: ModelGateway | None = None,
    ) -> None:
        self.database = database
        self.model_gateway = model_gateway or ModelGateway(database)
        # Explicit test doubles still take precedence. Production services see
        # only the provider-neutral gateway, which owns protocol and URL choice.
        self.llm_provider = llm_provider or self._llm_provider()
        self.vision_provider = vision_provider or self._vision_provider()

    async def analyze_task(self, task: ResearchTask, *, retry_failed: bool = False) -> list[AnalysisItemRead]:
        ensure_analysis_defaults(self.database)
        if task.status is ResearchTaskStatus.ANALYZING:
            raise RuntimeError("Analysis is already running for this research task")
        rankings = RankingService(self.database).rank_task(task.id)
        ranked = {item.content_item_id: item for board in rankings.boards if board.name == "Hot" for item in board.items}
        contents = list(self.database.scalars(select(ContentItem).where(ContentItem.research_task_id == task.id)))
        results: list[AnalysisItemRead] = []
        failures = False
        task.status = ResearchTaskStatus.ANALYZING
        task.error_message = None
        self.database.commit()
        for content in contents:
            record = self.database.scalar(select(ContentAnalysisRecord).where(ContentAnalysisRecord.content_item_id == content.id))
            if record is not None and record.analysis_error is None and record.text_analysis and record.content_analysis:
                results.append(self._response(content, record, ranked.get(content.id)))
                continue
            if record is not None and record.analysis_error and not retry_failed:
                failures = True
                results.append(self._response(content, record, ranked.get(content.id)))
                continue
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

    def read_task(self, task: ResearchTask) -> list[AnalysisItemRead]:
        """Return persisted analysis only; read endpoints must never invoke a model."""
        rankings = RankingService(self.database).rank_task(task.id)
        ranked = {item.content_item_id: item for board in rankings.boards if board.name == "Hot" for item in board.items}
        contents = list(self.database.scalars(select(ContentItem).where(ContentItem.research_task_id == task.id)))
        records = {
            record.content_item_id: record
            for record in self.database.scalars(
                select(ContentAnalysisRecord).join(ContentItem).where(ContentItem.research_task_id == task.id)
            )
        }
        return [
            self._response(content, records.get(content.id) or ContentAnalysisRecord(content_item_id=content.id, visual_analyses=[]), ranked.get(content.id))
            for content in contents
        ]

    async def trends_for_task(self, task: ResearchTask) -> TrendAnalysisRead:
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
        context = {"analysis_type": "text", "topic": task.topic, "platform": task.platform, "title": content.title or "", "text": content.text or ""}
        prompt = f"{self._prompt('text_analysis', task)}\n\n{TEXT_ANALYSIS_CONTRACT}"
        response = await self.llm_provider.generate_structured(prompt=prompt, context=context)
        return await self._validate_or_repair(
            model=TextAnalysis, response=response, prompt=prompt, context=context, provider=self.llm_provider,
        )

    async def _analyze_images(self, task: ResearchTask, content: ContentItem) -> list[VisualAnalysis]:
        analyses: list[VisualAnalysis] = []
        for local_path in content.local_image_paths or []:
            image_path = Path(local_path)
            if not image_path.is_file():
                logger.warning("local_analysis_image_missing content_id=%s", content.id)
                continue
            context = {"analysis_type": "visual", "topic": task.topic, "platform": task.platform, "title": content.title or "", "content_id": content.id}
            prompt = f"{self._prompt('visual_analysis', task)}\n\n{VISUAL_ANALYSIS_CONTRACT}"
            response = await self.vision_provider.analyze_image(
                image_path=image_path, prompt=prompt, context=context,
            )
            analyses.append(await self._validate_or_repair(
                model=VisualAnalysis, response=response, prompt=prompt, context=context,
                provider=self.vision_provider, image_path=image_path,
            ))
        return analyses

    def _prompt(self, purpose: str, task: ResearchTask) -> str:
        template = self.database.scalar(select(PromptTemplate).where(PromptTemplate.purpose == purpose, PromptTemplate.enabled.is_(True)))
        value = template.template if template else ""
        return value.replace("{topic}", task.topic).replace("{platform}", task.platform).replace("{research_goals}", task.research_goals or "")

    @staticmethod
    async def _validate_or_repair(
        *, model: type[TextAnalysis] | type[VisualAnalysis], response: dict[str, Any], prompt: str,
        context: dict[str, Any], provider: LLMProvider | VisionProvider, image_path: Path | None = None,
    ) -> TextAnalysis | VisualAnalysis:
        try:
            return model.model_validate(response)
        except ValidationError as original_error:
            repair_prompt = (
                f"The previous JSON did not satisfy the required contract. Repair it now.\n\n{prompt}\n\n"
                f"Previous JSON:\n{json.dumps(response, ensure_ascii=False)}\n\n"
                f"Validation errors:\n{str(original_error)[:3000]}"
            )
            if image_path is None:
                repaired = await provider.generate_structured(prompt=repair_prompt, context=context)  # type: ignore[union-attr]
            else:
                repaired = await provider.analyze_image(image_path=image_path, prompt=repair_prompt, context=context)  # type: ignore[union-attr]
            return model.model_validate(repaired)

    def _llm_provider(self) -> LLMProvider:
        return _GatewayLLMProvider(self.model_gateway) if self.model_gateway.has_candidate(purpose="llm") else MockLLMProvider()

    def _vision_provider(self) -> VisionProvider:
        return _GatewayVisionProvider(self.model_gateway) if self.model_gateway.has_candidate(purpose="vision") else MockVisionProvider()

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


class _GatewayLLMProvider:
    """Keeps the existing LLMProvider seam while delegating runtime routing."""

    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def generate_structured(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return await self.gateway.generate_structured(purpose="llm", prompt=prompt, context=context)


class _GatewayVisionProvider:
    """Keeps the existing VisionProvider seam while delegating runtime routing."""

    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def analyze_image(self, *, image_path: Path, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        return await self.gateway.generate_structured(
            purpose="vision", prompt=prompt, context=context, image_path=image_path,
        )
