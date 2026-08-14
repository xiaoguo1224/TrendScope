from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.time import as_shanghai_time
from app.models.research_task import ResearchTaskStatus


class ResearchTaskCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=500)
    keywords: list[str] = Field(min_length=1, max_length=30)
    time_range: str = Field(min_length=1, max_length=100)
    max_items: int = Field(default=50, ge=1, le=500)
    research_goals: str | None = Field(default=None, max_length=5000)


class ResearchTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    topic: str
    keywords: list[str]
    expanded_keywords: dict[str, list[str]] | None
    time_range: str
    max_items: int
    research_goals: str | None
    status: ResearchTaskStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    current_stage: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    collected_count: int = Field(default=0, ge=0)

    @field_serializer("created_at", "updated_at")
    def serialize_time(self, value: datetime) -> datetime:
        return as_shanghai_time(value)


class ContentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    research_task_id: int
    platform: str
    external_id: str
    url: str
    title: str | None
    text: str | None
    author_name: str | None
    published_at: datetime | None
    like_count: int | None
    favorite_count: int | None
    comment_count: int | None
    share_count: int | None
    view_count: int | None
    media_type: str | None
    image_urls: list[str]
    local_image_paths: list[str]
    video_urls: list[str]
    query_keyword: str | None
    collected_at: datetime
    raw_data: dict[str, object] | None

    @field_serializer("published_at", "collected_at")
    def serialize_time(self, value: datetime | None) -> datetime | None:
        return as_shanghai_time(value) if value is not None else None
