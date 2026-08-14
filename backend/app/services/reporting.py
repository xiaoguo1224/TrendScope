from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.configuration import ensure_analysis_defaults
from app.core.config import get_settings
from app.models.analysis import CreativeConceptRecord, ImagePromptRecord, ReportRecord
from app.models.configuration import AppSetting, PromptTemplate
from app.models.content import ContentItem
from app.models.research_task import ResearchTask
from app.schemas.analysis import RankingsRead, TaskAnalysisRead, TrendAnalysisRead
from app.schemas.reporting import CreativeConceptRead, ImagePromptRead, ReportRead
from app.services.ranking import RankingService
from app.services.task_analysis import TaskAnalysisService


class ReportingService:
    """Creates durable, text-only creative outputs from persisted research evidence."""

    def __init__(self, database: Session, *, reports_dir: Path | None = None) -> None:
        self.database = database
        self.reports_dir = reports_dir or get_settings().reports_dir

    async def concepts_for_task(self, task: ResearchTask) -> list[CreativeConceptRead]:
        concepts = self._concept_records(task.id)
        if not concepts:
            trends = TaskAnalysisService(self.database).trends(task)
            concepts = self._create_concepts(task, trends)
        return [CreativeConceptRead.model_validate(item) for item in concepts]

    async def prompts_for_task(self, task: ResearchTask) -> list[ImagePromptRead]:
        await self.concepts_for_task(task)
        concepts = self._concept_records(task.id)
        trends = TaskAnalysisService(self.database).trends(task)
        visual_evidence = self._visual_evidence(TaskAnalysisService(self.database).read(task), trends)
        existing_rows = self.database.execute(
            select(ImagePromptRecord, CreativeConceptRecord)
            .join(CreativeConceptRecord, ImagePromptRecord.creative_concept_id == CreativeConceptRecord.id)
            .where(CreativeConceptRecord.research_task_id == task.id)
            .order_by(CreativeConceptRecord.position)
        ).all()
        existing = {prompt.creative_concept_id: prompt for prompt, _ in existing_rows}
        defaults = self._defaults()
        for concept in concepts:
            if concept.id not in existing:
                self.database.add(self._create_prompt(task, concept, defaults, visual_evidence))
        self.database.commit()
        prompt_rows = self.database.execute(
            select(ImagePromptRecord, CreativeConceptRecord)
            .join(CreativeConceptRecord, ImagePromptRecord.creative_concept_id == CreativeConceptRecord.id)
            .where(CreativeConceptRecord.research_task_id == task.id)
            .order_by(CreativeConceptRecord.position)
        ).all()
        return [self._prompt_response(prompt, concept) for prompt, concept in prompt_rows]

    async def report_for_task(self, task: ResearchTask, *, regenerate: bool = False) -> ReportRead:
        persisted = self.database.scalar(select(ReportRecord).where(ReportRecord.research_task_id == task.id))
        if persisted is None or regenerate:
            trends = TaskAnalysisService(self.database).trends(task)
            concepts = await self.concepts_for_task(task)
            prompts = await self.prompts_for_task(task)
            rankings = RankingService(self.database).rank_task(task.id)
            analysis = TaskAnalysisService(self.database).read(task)
            content, limitations = self._report_content(task, rankings, analysis, trends, concepts, prompts)
            markdown = self._markdown(content)
            report_path, prompts_path = self._write_exports(task.id, content, markdown, prompts)
            if persisted is None:
                persisted = ReportRecord(
                    research_task_id=task.id, content=content, markdown=markdown, limitations=limitations,
                    report_path=report_path, prompts_path=prompts_path,
                )
                self.database.add(persisted)
            else:
                persisted.content = content
                persisted.markdown = markdown
                persisted.limitations = limitations
                persisted.report_path = report_path
                persisted.prompts_path = prompts_path
            self.database.commit()
            self.database.refresh(persisted)
        return ReportRead(
            task_id=task.id, content=persisted.content, markdown=persisted.markdown,
            limitations=persisted.limitations, report_path=persisted.report_path,
            prompts_path=persisted.prompts_path, generated_at=persisted.generated_at,
        )

    def _create_concepts(self, task: ResearchTask, trends: TrendAnalysisRead) -> list[CreativeConceptRecord]:
        defaults = self._defaults()
        count = max(1, min(20, int(defaults.get("concept_count", 10))))
        sources = {
            "hot_topics": trends.hot_topics, "rising_topics": trends.rising_topics,
            "visual_patterns": trends.visual_patterns, "copywriting_patterns": trends.copywriting_patterns,
            "audience_patterns": trends.audience_patterns, "scenario_patterns": trends.scenario_patterns,
            "style_patterns": trends.style_patterns, "domain_patterns": trends.domain_patterns,
        }
        basis = [f"{label}: {value}" for label, values in sources.items() for value in values[:3]]
        if not basis:
            basis = [f"research_keywords: {keyword}" for keyword in task.keywords]
        topic_terms = sources["hot_topics"] or sources["rising_topics"] or list(task.keywords) or [task.topic]
        visual_terms = sources["visual_patterns"] or sources["style_patterns"] or ["clear visual hierarchy"]
        copy_terms = sources["copywriting_patterns"] or ["clear topic-led opening"]
        audiences = sources["audience_patterns"]
        scenarios = sources["scenario_patterns"]
        guidance = self._template("creative_concept", task, {
            "trend_basis": "; ".join(basis),
            "visual_context": "; ".join([str(item) for item in visual_terms]),
            "domain_attributes": "; ".join([str(item) for item in sources["domain_patterns"]]),
        })
        records: list[CreativeConceptRecord] = []
        for position in range(1, count + 1):
            topic_term = topic_terms[(position - 1) % len(topic_terms)]
            visual_term = visual_terms[(position - 1) % len(visual_terms)]
            copy_term = copy_terms[(position - 1) % len(copy_terms)]
            record = CreativeConceptRecord(
                research_task_id=task.id, position=position, name=f"{task.topic}: {topic_term} direction {position}",
                concept=(
                    f"An original {task.topic} creative direction that combines the observed topic signal "
                    f"'{topic_term}' with '{copy_term}'. Guidance: {guidance}"
                ),
                target_audience=audiences[:3], scenario=scenarios[:3], style=str(visual_term),
                main_elements=list(dict.fromkeys([str(topic_term), str(visual_term), str(copy_term)])),
                trend_basis=basis[:8],
                differentiation="Combines multiple aggregated research signals instead of reproducing any single collected item.",
            )
            self.database.add(record)
            records.append(record)
        self.database.commit()
        for record in records:
            self.database.refresh(record)
        return records

    def _create_prompt(
        self, task: ResearchTask, concept: CreativeConceptRecord, defaults: dict[str, object], visual_evidence: dict[str, str],
    ) -> ImagePromptRecord:
        language = str(defaults.get("prompt_language", "English"))
        style = str(defaults.get("prompt_style", "editorial lifestyle photography"))
        elements = ", ".join(concept.main_elements) or "research-grounded visual elements"
        audience = ", ".join(concept.target_audience) or "the intended audience"
        scenario = ", ".join(concept.scenario) or "an authentic everyday context"
        guidance = self._template("image_prompt", task, {
            "concept_name": concept.name,
            "trend_basis": "; ".join(concept.trend_basis),
            **visual_evidence,
        })
        common = (
            f"{concept.name}, {style}, {elements}, for {audience}, {language} prompt. "
            f"Visual evidence: {visual_evidence['visual_context']}. "
            f"Domain attributes: {visual_evidence['domain_attributes']}. Guidance: {guidance}"
        )
        return ImagePromptRecord(
            creative_concept_id=concept.id, output_language=language, output_style=style,
            hero_prompt=f"Hero image: {common}, single clear focal subject, high-quality composition.",
            detail_prompt=f"Detail image: close-up of {elements}, tactile material and meaningful details, {style}.",
            lifestyle_prompt=f"Lifestyle image: {concept.name} in {scenario}, natural human context, {style}.",
            cover_prompt=f"Cover image: {common}, generous negative space for headline, instantly readable hierarchy.",
            negative_prompt="No logos, no watermarks, no copied source imagery, no distorted anatomy, no unreadable text, no unsafe content.",
        )

    def _report_content(
        self, task: ResearchTask, rankings: RankingsRead, analysis: TaskAnalysisRead, trends: TrendAnalysisRead,
        concepts: list[CreativeConceptRead], prompts: list[ImagePromptRead],
    ) -> tuple[dict[str, Any], list[str]]:
        items = self.database.scalars(select(ContentItem).where(ContentItem.research_task_id == task.id)).all()
        boards = {board.name: [item.model_dump(mode="json") for item in board.items[:10]] for board in rankings.boards}
        limitations: list[str] = []
        if not items:
            limitations.append("No public content was collected, so rankings and trend evidence are empty.")
        if trends.insufficient_data and trends.limitation:
            limitations.append(trends.limitation)
        if analysis.analysis_error:
            limitations.append(analysis.analysis_error)
        if not analysis.visual_summary:
            limitations.append("No local images were available for visual analysis.")
        limitations.extend(analysis.limitations)
        content: dict[str, Any] = {
            "research_task": {"id": task.id, "platform": task.platform, "topic": task.topic, "time_range": task.time_range, "research_goals": task.research_goals},
            "data_overview": {"collected_content_count": len(items), "analyzed_content_count": trends.analyzed_content_count, "image_analysis_count": 1 if analysis.visual_summary else 0},
            "search_keywords": {"input": task.keywords, "expanded": task.expanded_keywords or {}},
            "hot": boards.get("Hot", []), "rising": boards.get("Rising", []),
            "popular_articles": [],
            "popular_images": [],
            "copywriting_structure_analysis": analysis.copywriting_summary,
            "visual_structure_analysis": analysis.visual_summary,
            "popularity_reason_analysis": analysis.popularity_summary,
            "current_hot_trends": trends.hot_topics,
            "recent_rising_trends": trends.rising_topics,
            "audience_preferences": trends.audience_patterns,
            "reusable_patterns": {"copywriting": trends.copywriting_patterns, "visual": trends.visual_patterns, "scenarios": trends.scenario_patterns, "styles": trends.style_patterns, "domain": trends.domain_patterns},
            "recommended_creative_directions": [item.name for item in concepts],
            "creative_concepts": [item.model_dump(mode="json") for item in concepts],
            "image_prompts": [item.model_dump(mode="json") for item in prompts],
            "next_round_recommended_keywords": list(dict.fromkeys([*trends.rising_topics, *trends.hot_topics, *task.keywords]))[:20],
            "data_limitations": limitations,
        }
        return content, limitations

    def _write_exports(self, task_id: int, content: dict[str, Any], markdown: str, prompts: list[ImagePromptRead]) -> tuple[str, str]:
        directory = self.reports_dir / str(task_id)
        directory.mkdir(parents=True, exist_ok=True)
        report_path, json_path, prompts_path = directory / "report.md", directory / "report.json", directory / "prompts.md"
        report_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(content, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        prompts_path.write_text(self._prompts_markdown(prompts), encoding="utf-8")
        return report_path.as_posix(), prompts_path.as_posix()

    @staticmethod
    def _markdown(content: dict[str, Any]) -> str:
        labels = {
            "research_task": "研究任务", "data_overview": "数据概览", "search_keywords": "搜索关键词", "hot": "Hot", "rising": "Rising",
            "popular_articles": "热门文章", "popular_images": "热门图片", "copywriting_structure_analysis": "文案结构分析", "visual_structure_analysis": "视觉结构分析",
            "popularity_reason_analysis": "爆款原因分析", "current_hot_trends": "当前热门趋势", "recent_rising_trends": "近期上升趋势",
            "audience_preferences": "用户偏好", "reusable_patterns": "可复用规律", "recommended_creative_directions": "推荐创作方向",
            "creative_concepts": "Creative Concepts", "image_prompts": "AI 图片 Prompt", "next_round_recommended_keywords": "下一轮推荐关键词", "data_limitations": "数据限制",
        }
        return "\n\n".join(f"## {labels[key]}\n\n```json\n{json.dumps(value, ensure_ascii=False, indent=2, default=str)}\n```" for key, value in content.items()) + "\n"

    @staticmethod
    def _prompts_markdown(prompts: list[ImagePromptRead]) -> str:
        sections = []
        for prompt in prompts:
            sections.append(
                f"## Concept\n\n{prompt.concept_name}\n\n## Trend Basis\n\n" + "\n".join(f"- {item}" for item in prompt.trend_basis)
                + f"\n\n## Hero Prompt\n\n{prompt.hero_prompt}\n\n## Detail Prompt\n\n{prompt.detail_prompt}\n\n## Lifestyle Prompt\n\n{prompt.lifestyle_prompt}\n\n## Cover Prompt\n\n{prompt.cover_prompt}\n\n## Negative Prompt\n\n{prompt.negative_prompt}"
            )
        return "\n\n---\n\n".join(sections) + ("\n" if sections else "")

    def _defaults(self) -> dict[str, object]:
        ensure_analysis_defaults(self.database)
        setting = self.database.scalar(select(AppSetting).where(AppSetting.key == "report_defaults"))
        return setting.value if setting and isinstance(setting.value, dict) else {}

    def _template(self, purpose: str, task: ResearchTask | None, context: dict[str, str] | None = None) -> str:
        template = self.database.scalar(select(PromptTemplate).where(PromptTemplate.purpose == purpose, PromptTemplate.enabled.is_(True)))
        value = template.template if template else ""
        values = {
            "topic": task.topic if task else "",
            "platform": task.platform if task else "",
            "research_goals": (task.research_goals or "") if task else "",
            **(context or {}),
        }
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", self._compact_text(replacement))
        return self._compact_text(value)

    @classmethod
    def _visual_evidence(cls, analysis: TaskAnalysisRead, trends: TrendAnalysisRead) -> dict[str, str]:
        visual_details = [value for value in [analysis.visual_summary, *trends.visual_patterns, *trends.style_patterns] if value]
        domain_attributes = list(trends.domain_patterns)
        return {
            "visual_context": cls._compact_text("; ".join(dict.fromkeys(visual_details)) or "No visual evidence was available."),
            "domain_attributes": cls._compact_text("; ".join(dict.fromkeys(domain_attributes)) or "No domain-specific attributes were available."),
        }

    @staticmethod
    def _compact_text(value: object, limit: int = 1000) -> str:
        return " ".join(str(value).split())[:limit]

    def _concept_records(self, task_id: int) -> list[CreativeConceptRecord]:
        return list(self.database.scalars(select(CreativeConceptRecord).where(CreativeConceptRecord.research_task_id == task_id).order_by(CreativeConceptRecord.position)))

    @staticmethod
    def _prompt_response(prompt: ImagePromptRecord, concept: CreativeConceptRecord) -> ImagePromptRead:
        return ImagePromptRead.model_validate({**{key: getattr(prompt, key) for key in ImagePromptRead.model_fields if key not in {"concept_name", "trend_basis"}}, "concept_name": concept.name, "trend_basis": concept.trend_basis})
