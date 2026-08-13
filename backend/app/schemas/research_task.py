from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
