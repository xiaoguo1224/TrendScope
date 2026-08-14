from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TextAnalysis(BaseModel):
    hook_type: str
    title_structure: str
    opening_hook: str
    writing_style: str
    emotion: str
    pain_points: list[str]
    benefits: list[str]
    target_audience: list[str]
    scenario: list[str]
    cta: str | None = None
    hashtags: list[str]
    topic_tags: list[str]
    reusable_patterns: list[str]


class VisualAnalysis(BaseModel):
    subject: str
    main_colors: list[str]
    secondary_colors: list[str]
    style: str
    composition: str
    camera_angle: str
    lighting: str
    background: str
    visual_focus: str
    scene: str
    mood: str
    target_audience: list[str]
    notable_elements: list[str]
    reusable_visual_patterns: list[str]
    domain_attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)


class ContentAnalysis(BaseModel):
    why_it_may_be_popular: str
    core_content_elements: list[str]
    core_visual_elements: list[str]
    target_audience: list[str]
    emotional_value: str
    reusable_patterns: list[str]
    trend_tags: list[str]
    evidence: list[str]
    limitations: list[str]


class MetricVelocity(BaseModel):
    value_per_hour: float | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class RankedContentItem(BaseModel):
    content_item_id: int
    title: str | None
    url: str
    metrics: dict[str, int]
    metric_velocities: dict[str, MetricVelocity]
    engagement_score: float
    freshness_score: float
    growth_score: float | None
    hot_score: float


class RankingBoard(BaseModel):
    name: str
    metric: str | None = None
    items: list[RankedContentItem]


class RankingsRead(BaseModel):
    task_id: int
    config_name: str
    boards: list[RankingBoard]


class AnalysisItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_item_id: int
    title: str | None
    url: str
    local_image_paths: list[str]
    objective_facts: dict[str, Any]
    text_analysis: TextAnalysis | None = None
    visual_analyses: list[VisualAnalysis] = Field(default_factory=list)
    content_analysis: ContentAnalysis | None = None
    analysis_error: str | None = None
    analyzed_at: datetime | None = None


class TaskAnalysisRead(BaseModel):
    task_id: int
    copywriting_summary: str | None = None
    visual_summary: str | None = None
    audience_summary: str | None = None
    popularity_summary: str | None = None
    reusable_patterns: list[str] = Field(default_factory=list)
    trend_tags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    hot_topics: list[str] = Field(default_factory=list)
    rising_topics: list[str] = Field(default_factory=list)
    visual_patterns: list[str] = Field(default_factory=list)
    copywriting_patterns: list[str] = Field(default_factory=list)
    audience_patterns: list[str] = Field(default_factory=list)
    scenario_patterns: list[str] = Field(default_factory=list)
    style_patterns: list[str] = Field(default_factory=list)
    domain_patterns: list[str] = Field(default_factory=list)
    analysis_error: str | None = None
    analyzed_at: datetime | None = None


class TrendAnalysisRead(BaseModel):
    task_id: int
    insufficient_data: bool
    limitation: str | None = None
    analyzed_content_count: int
    hot_topics: list[str] = Field(default_factory=list)
    rising_topics: list[str] = Field(default_factory=list)
    visual_patterns: list[str] = Field(default_factory=list)
    copywriting_patterns: list[str] = Field(default_factory=list)
    audience_patterns: list[str] = Field(default_factory=list)
    scenario_patterns: list[str] = Field(default_factory=list)
    style_patterns: list[str] = Field(default_factory=list)
    domain_patterns: list[str] = Field(default_factory=list)
