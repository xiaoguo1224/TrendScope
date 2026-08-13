from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ResearchTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXPANDING_QUERY = "EXPANDING_QUERY"
    COLLECTING = "COLLECTING"
    RANKING = "RANKING"
    ANALYZING = "ANALYZING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(100), index=True)
    topic: Mapped[str] = mapped_column(String(500))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    expanded_keywords: Mapped[dict[str, list[str]] | None] = mapped_column(JSON, nullable=True)
    time_range: Mapped[str] = mapped_column(String(100))
    max_items: Mapped[int] = mapped_column(Integer)
    research_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ResearchTaskStatus] = mapped_column(Enum(ResearchTaskStatus), default=ResearchTaskStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    content_items: Mapped[list["ContentItem"]] = relationship(back_populates="research_task", cascade="all, delete-orphan")
