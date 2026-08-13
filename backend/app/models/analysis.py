from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContentAnalysisRecord(Base):
    """Persisted, provider-independent analysis for one collected content item."""

    __tablename__ = "content_analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), unique=True, index=True)
    text_analysis: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    visual_analyses: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    content_analysis: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrendAnalysisRecord(Base):
    """Latest cross-content trend result for a research task."""

    __tablename__ = "trend_analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_task_id: Mapped[int] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"), unique=True, index=True)
    result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CreativeConceptRecord(Base):
    """A task-scoped creative direction synthesized from aggregated evidence."""

    __tablename__ = "creative_concept_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_task_id: Mapped[int] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(500))
    concept: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[list[str]] = mapped_column(JSON, default=list)
    scenario: Mapped[list[str]] = mapped_column(JSON, default=list)
    style: Mapped[str] = mapped_column(String(500))
    main_elements: Mapped[list[str]] = mapped_column(JSON, default=list)
    trend_basis: Mapped[list[str]] = mapped_column(JSON, default=list)
    differentiation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ImagePromptRecord(Base):
    """Text-only image prompts for a persisted creative concept; never generated media."""

    __tablename__ = "image_prompt_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    creative_concept_id: Mapped[int] = mapped_column(ForeignKey("creative_concept_records.id", ondelete="CASCADE"), unique=True, index=True)
    output_language: Mapped[str] = mapped_column(String(50))
    output_style: Mapped[str] = mapped_column(String(500))
    hero_prompt: Mapped[str] = mapped_column(Text)
    detail_prompt: Mapped[str] = mapped_column(Text)
    lifestyle_prompt: Mapped[str] = mapped_column(Text)
    cover_prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportRecord(Base):
    """Metadata and structured report snapshot; files are reproducible exports of this record."""

    __tablename__ = "report_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_task_id: Mapped[int] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"), unique=True, index=True)
    content: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    markdown: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    report_path: Mapped[str] = mapped_column(String(2048))
    prompts_path: Mapped[str] = mapped_column(String(2048))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
