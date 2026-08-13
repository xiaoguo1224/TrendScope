from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("research_task_id", "platform", "external_id", name="uq_task_platform_external"),
        Index("ix_content_items_task_published", "research_task_id", "published_at"),
        Index("ix_content_items_task_collected", "research_task_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    research_task_id: Mapped[int] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favorite_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    local_image_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    video_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    query_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    raw_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    research_task: Mapped["ResearchTask"] = relationship(back_populates="content_items")
    metric_snapshots: Mapped[list["ContentMetricSnapshot"]] = relationship(back_populates="content_item", cascade="all, delete-orphan")


class ContentMetricSnapshot(Base):
    __tablename__ = "content_metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favorite_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    content_item: Mapped[ContentItem] = relationship(back_populates="metric_snapshots")
