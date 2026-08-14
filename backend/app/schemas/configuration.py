from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppSettingUpsert(BaseModel):
    value: object
    description: str | None = Field(default=None, max_length=2000)


class AppSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: object
    description: str | None
    updated_at: datetime


class PlatformConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    search_url_template: str | None = Field(default=None, max_length=2048)
    selectors: dict[str, str | dict[str, str]] = Field(default_factory=dict)
    parser_rules: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True


class PlatformConfigRead(PlatformConfigCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PlatformConfigTestRequest(BaseModel):
    query: str = Field(default="测试关键词", min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=50)


class PlatformConfigTestRead(BaseModel):
    success: bool
    search_result_count: int = 0
    first_result: dict[str, Any] | None = None
    detail_result: dict[str, Any] | None = None
    message: str | None = None


class BrowserConnectionTestRead(BaseModel):
    success: bool
    message: str


class AIProviderConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: str = Field(min_length=1, max_length=30)
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    protocol: Literal["auto", "openai_responses", "openai_chat", "anthropic_messages", "gemini", "ollama_generate", "ollama_chat"] = "auto"
    capabilities: dict[str, bool] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0, le=10000)
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    enabled: bool = False


class AIProviderConfigRead(AIProviderConfigCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    api_key: str | None = None

    @field_validator("api_key", mode="before")
    @classmethod
    def mask_api_key(cls, value: str | None) -> str | None:
        if not value:
            return None
        return "*" * max(0, len(value) - 4) + value[-4:]


class AIProviderConfigTestRead(BaseModel):
    success: bool
    endpoint: str
    request_preview: str | None = None
    response_preview: str | None = None
    message: str


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    template: str = Field(min_length=1)
    enabled: bool = True


class PromptTemplateRead(PromptTemplateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RankingConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    like_weight: float = 1.0
    favorite_weight: float = 1.2
    comment_weight: float = 1.5
    share_weight: float = 1.5
    view_weight: float = 0.1
    freshness_half_life_hours: int = Field(default=72, ge=1)
    growth_window_hours: int = Field(default=24, ge=1)


class RankingConfigRead(RankingConfigCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
