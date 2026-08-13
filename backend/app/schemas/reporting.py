from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreativeConceptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    name: str
    concept: str
    target_audience: list[str] = Field(default_factory=list)
    scenario: list[str] = Field(default_factory=list)
    style: str
    main_elements: list[str] = Field(default_factory=list)
    trend_basis: list[str] = Field(default_factory=list)
    differentiation: str
    created_at: datetime | None = None


class ImagePromptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creative_concept_id: int
    concept_name: str
    trend_basis: list[str] = Field(default_factory=list)
    output_language: str
    output_style: str
    hero_prompt: str
    detail_prompt: str
    lifestyle_prompt: str
    cover_prompt: str
    negative_prompt: str
    created_at: datetime | None = None


class ReportRead(BaseModel):
    task_id: int
    content: dict[str, Any]
    markdown: str
    limitations: list[str] = Field(default_factory=list)
    report_path: str
    prompts_path: str
    generated_at: datetime | None = None
