from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Text, func
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
