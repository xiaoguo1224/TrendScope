from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_tools import TaskAnalysisToolRegistry
from app.models.analysis import CreativeConceptRecord, ReportRecord, TaskAnalysisRecord
from app.models.research_task import ResearchTask, ResearchTaskStatus
from app.schemas.analysis import TaskAnalysisRead, TrendAnalysisRead
from app.services.analysis import AnalysisService
from app.services.task_analysis_agent import TaskAnalysisAgent, TaskAnalysisResult

logger = logging.getLogger(__name__)


class TaskAnalysisService:
    """Persists one model-authored synthesis for a whole research task.

    Evidence is exposed through a bounded, read-only task-scoped registry.  No
    content-level model result is produced or read from this service.
    """

    def __init__(self, database: Session) -> None:
        self.database = database

    async def run(self, task: ResearchTask, *, regenerate: bool = False) -> TaskAnalysisRead:
        existing = self._record(task.id)
        if existing and existing.result and not existing.analysis_error and not regenerate:
            return self._response(task.id, existing)
        if task.status is ResearchTaskStatus.ANALYZING:
            raise RuntimeError("Analysis is already running for this research task")

        task.status = ResearchTaskStatus.ANALYZING
        task.error_message = None
        self.database.commit()
        record = existing or TaskAnalysisRecord(research_task_id=task.id)
        if existing is None:
            self.database.add(record)
        try:
            providers = AnalysisService(self.database)
            result = await TaskAnalysisAgent(
                TaskAnalysisToolRegistry(self.database, task),
                llm_provider=providers.llm_provider,
                vision_provider=providers.vision_provider,
            ).run()
            record.result = result.model_dump(mode="json")
            record.analysis_error = None
            task.status = ResearchTaskStatus.COMPLETED
            # Concepts, prompts and reports are all derived from the prior task
            # synthesis.  Do not serve stale creative output after an explicit
            # regeneration; they are recreated lazily from this new summary.
            for concept in self.database.scalars(select(CreativeConceptRecord).where(CreativeConceptRecord.research_task_id == task.id)):
                self.database.delete(concept)
            report = self.database.scalar(select(ReportRecord).where(ReportRecord.research_task_id == task.id))
            if report is not None:
                self.database.delete(report)
            self.database.commit()
            self.database.refresh(record)
            return self._response(task.id, record)
        except Exception as error:
            self.database.rollback()
            record = self._record(task.id) or record
            if record not in self.database:
                self.database.add(record)
            record.result = None
            record.analysis_error = self._safe_error(error)
            task = self.database.get(ResearchTask, task.id) or task
            task.status = ResearchTaskStatus.PARTIAL
            task.error_message = "Task-level analysis failed"
            self.database.commit()
            logger.warning("task_analysis_failed task_id=%s", task.id, exc_info=True)
            return self._response(task.id, record)

    def read(self, task: ResearchTask) -> TaskAnalysisRead:
        """Read persisted data only; this method never calls an AI provider."""
        record = self._record(task.id)
        return self._response(task.id, record) if record else TaskAnalysisRead(task_id=task.id)

    def trends(self, task: ResearchTask) -> TrendAnalysisRead:
        analysis = self.read(task)
        if analysis.analysis_error:
            return TrendAnalysisRead(task_id=task.id, insufficient_data=True, limitation=analysis.analysis_error, analyzed_content_count=0)
        if not analysis.copywriting_summary and not analysis.visual_summary:
            return TrendAnalysisRead(task_id=task.id, insufficient_data=True, limitation="Run task-level analysis before requesting model-authored trends.", analyzed_content_count=0)
        return TrendAnalysisRead(
            task_id=task.id, insufficient_data=False, analyzed_content_count=1,
            hot_topics=analysis.hot_topics or analysis.trend_tags,
            rising_topics=analysis.rising_topics,
            visual_patterns=analysis.visual_patterns,
            copywriting_patterns=analysis.copywriting_patterns or analysis.reusable_patterns,
            audience_patterns=analysis.audience_patterns,
            scenario_patterns=analysis.scenario_patterns,
            style_patterns=analysis.style_patterns,
            domain_patterns=analysis.domain_patterns,
        )

    def _record(self, task_id: int) -> TaskAnalysisRecord | None:
        return self.database.scalar(select(TaskAnalysisRecord).where(TaskAnalysisRecord.research_task_id == task_id))

    @staticmethod
    def _response(task_id: int, record: TaskAnalysisRecord) -> TaskAnalysisRead:
        payload = record.result if isinstance(record.result, dict) else {}
        return TaskAnalysisRead.model_validate({"task_id": task_id, **payload, "analysis_error": record.analysis_error, "analyzed_at": record.analyzed_at})

    @staticmethod
    def _safe_error(error: Exception) -> str:
        return str(error)[:500] or error.__class__.__name__
